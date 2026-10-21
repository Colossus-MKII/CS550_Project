"""Reference-only stratum for native SAM failures without a YOLO correction.

The approved proposal reports prompt SOURCES separately. Missing detector
boxes must not censor all otherwise valid SAM failures or be fabricated.
Keep the same failure/state/visibility rules; label this unavailable-source
stratum explicitly, freeze BEFORE inference, and never pool box-source wins.
"""

import argparse
from contextlib import redirect_stdout, redirect_stderr
from datetime import datetime, timezone
import gc
from pathlib import Path
import traceback

from . import PACKAGE_ROOT
from .common import digest, load_predictions, write_json
from .dataset import read_manifest, load_ground_truth
from .natural_events import fixed_id_curve, failure_label, has_correct_run, read_json
from .selection_preflight import inspect_event


def freeze(coverage, baselines, data_root, split, previous, output):
    """Choose earliest valid reference-only B event per coverage-qualified key."""
    coverage,baselines,data_root,split,previous,output=map(Path,(coverage,baselines,data_root,split,previous,output))
    if output.exists():
        raise FileExistsError("New reference-only archive required")
    audit=read_json(coverage)
    assert audit["split_sha256"] == digest(split)
    development={r["video_id"] for r in read_json(split)["splits"]["development"]}
    old={e["video_id"] for e in read_json(previous)["events"]}
    events=[]
    for vid,gid in audit["keys"]["complete_30_visible_followup"]:
        assert vid in development and vid!=2967
        source=baselines/str(vid)
        summary=read_json(source/"summary.json")
        assert summary["status"]=="inference_and_scoring_completed" and summary.get("sam_cpu_offload_guard")
        _,rows,_=read_manifest(data_root,[vid])
        gt=load_ground_truth(data_root,rows[0])
        category=next(o.category for f in gt for o in f if o.identity==gid)
        predictions={m:load_predictions(source/str(vid)/m) for m in ("A0","B0","YOLO")}
        curves={m:fixed_id_curve(gt,predictions[m],gid,category)[0] for m in ("A0","B0")}
        trace=read_json(source/str(vid)/"A0/state-trace.json")
        log=read_json(source/str(vid)/"B0/event-log.json")
        for t in range(5,len(gt)-30):
            if failure_label(curves["B0"],t)!="persistent_failure" or not all(has_correct_run(curves[m][:t-2]) for m in curves):
                continue
            if not all(any(o.identity==gid for o in gt[s]) for s in range(t,t+31)):
                continue
            e=inspect_event(gt,predictions,trace,log,summary["configuration"],
                            dict(video_id=vid,gt_id=gid,category=category,frame=t))
            if not e["eligible_common_state"] or e["yolo_correction"] is not None:
                continue
            eid=f"S{len(events)+1:02d}"
            e.pop("B0_future_target_actions",None)
            e.update(event_id=eid,name=f"{eid}-reference-only-{vid}-GT{gid}-t{t}",
                     scene="natural_failure_YOLO_unavailable",labels={m:failure_label(curves[m],t) for m in curves},
                     recent_three_iou={m:curves[m][t-2:t+1] for m in curves},
                     baseline_folder=str(source.resolve()),baseline_summary_sha256=digest(source/"summary.json"),
                     reused_video_from_16=vid in old,visible_followup=30)
            events.append(e)
            break
    if not events:
        raise ValueError("No eligible reference-only event; do not invent a prompt")
    output.mkdir(parents=True)
    frozen={
        "status":"reference_only_frozen_before_HR", "created_utc":datetime.now(timezone.utc).isoformat(),
        "events":events,"coverage_sha256":digest(coverage),"split_sha256":digest(split),
        "conditions":["reference"],"data_root":str(data_root.resolve()),
        "selection_source_sha256":digest(Path(__file__)),
        "limitations":["Separate source-availability stratum, not part of the balanced two-source batch.",
                       "Reference intervention uses GT for diagnostic routing; not automatic deployment.",
                       "Selected from native failures, not H/R outcomes; reused videos are not independent of earlier studies."],
    }
    write_json(output/"frozen-events.json",frozen)
    base=read_json(PACKAGE_ROOT/"defaults/recovery_long_normal.json")
    records=[]
    for e in events:
        config={**base,"conditions":["reference"],"role":"native_SAM_failure_reference_only_YOLO_unavailable",
                "frozen_selection_sha256":digest(output/"frozen-events.json"),
                "events":[{k:e[k] for k in ("name","video_id","gt_id","category","frame")}]}
        path=output/"configs"/(e["name"]+".json")
        write_json(path,config)
        records.append({"event_id":e["event_id"],"name":e["name"],"video_id":e["video_id"],
                        "scene":e["scene"],"baseline":e["baseline_folder"],"config_file":str(path.resolve()),
                        "config_sha256":digest(path),"status":"prepared"})
    plan={"status":"prepared","events":records,"conditions":["reference"],"window":30,
          "data_root":str(data_root.resolve()),"frozen_selection_sha256":digest(output/"frozen-events.json"),
          "repeat_event_id":records[0]["event_id"],"expected_branches":len(records)*4}
    write_json(output/"cohort.json",plan)
    return plan


def execute(args):
    import torch
    from .recovery import execute as run,make_parser
    from .recovery_report import build
    from .recovery_repeat import compare

    if not torch.cuda.is_available() or "3080" not in torch.cuda.get_device_name(0):
        raise RuntimeError("Local RTX3080 only")
    output=args.output
    plan=freeze(args.coverage,args.baselines,args.data_root,args.split,args.previous,output)
    plan.update(status="running",device=torch.cuda.get_device_name(0))
    write_json(output/"cohort.json",plan)
    def run_one(row,destination,log_name):
        assert digest(row["config_file"])==row["config_sha256"]
        command=make_parser().parse_args(["--baseline",row["baseline"],"--config",row["config_file"],
                                        "--data-root",plan["data_root"],"--device","cuda:0","--output",str(destination)])
        with (output/log_name).open("w",encoding="utf-8") as stream,redirect_stdout(stream),redirect_stderr(stream):
            run(command)
            check=build(destination,Path(plan["data_root"]))
        summary=read_json(destination/"summary.json")
        assert len(summary["branches"])==4 and summary["events"][0]["prefix_exact_replay"]
        assert summary["events"][0]["corrections"]["yolo"] is None
        assert not any(summary["synchronized_reference"]["historical_B0_different_frames"].values())
        gc.collect();torch.cuda.empty_cache()
        return check
    try:
        for row in plan["events"]:
            print("Reference-only native failure",row["name"],flush=True)
            destination=output/"events"/row["name"]
            check=run_one(row,destination,row["name"]+".log")
            row.update(status="completed",folder=str(destination.resolve()),verification=check,branches=4)
            write_json(output/"cohort.json",plan)
        row=plan["events"][0]
        repeated=output/"repeat"/row["name"]
        run_one(row,repeated,"repeat.log")
        repeat=compare(Path(row["folder"]),repeated)
        write_json(output/"repeat-verification.json",repeat)
        plan.update(status="completed",actual_branches=len(plan["events"])*4,repeat_branches=4,repeat_verification=repeat)
        write_json(output/"cohort.json",plan)
        print("Reference-only completed; no YOLO correction fabricated",flush=True)
    except Exception:
        plan.update(status="failed_preserved",error=traceback.format_exc())
        write_json(output/"cohort.json",plan)
        raise


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("coverage","baselines","data-root","split","previous","output"):
        p.add_argument("--"+name,type=Path,required=True)
    execute(p.parse_args(argv))


if __name__=="__main__":
    main()
