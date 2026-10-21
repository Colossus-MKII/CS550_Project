"""Explain SAM event-coverage gaps using NATIVE predictions, never H/R wins.

Counts are distinct (video, GT target) keys satisfying each nested criterion
at at least one step, NOT independent videos or a population failure rate.
Late errors/deleted targets must not be silently relabelled as 30-step events.
"""

import argparse
from pathlib import Path

from .common import digest, load_predictions, write_json
from .dataset import read_manifest, load_ground_truth
from .natural_events import fixed_id_curve, failure_label, has_correct_run, read_json
from .selection_preflight import inspect_event


STAGES = ("B_persistent_anywhere", "B_state_retained", "both_previously_three_correct",
          "common_operable_states", "complete_30_visible_followup", "YOLO_box_available")


def inspect_queue(queue_path, baselines, data_root, split_path, output):
    queue_path, baselines, data_root, split_path, output = map(
        Path, (queue_path, baselines, data_root, split_path, output))
    if output.exists():
        raise FileExistsError("Preserve earlier coverage audits")
    queue, split = read_json(queue_path), read_json(split_path)
    development = {r["video_id"] for r in split["splits"]["development"]}
    assert queue["split_sha256"] == digest(split_path)
    assert set(queue["video_ids"]) <= development
    stages = {s:set() for s in STAGES}
    first_examples = []
    for vid in sorted(set(queue["video_ids"])-{2967}):
        source = baselines / str(vid)
        summary = read_json(source/"summary.json")
        assert summary["status"] == "inference_and_scoring_completed" and summary.get("sam_cpu_offload_guard")
        _, records, _ = read_manifest(data_root,[vid])
        gt = load_ground_truth(data_root, records[0])
        folder = source/str(vid)
        predictions = {m:load_predictions(folder/m) for m in ("A0","B0","YOLO")}
        trace,log = read_json(folder/"A0/state-trace.json"),read_json(folder/"B0/event-log.json")
        for gid, category in sorted({(o.identity,o.category) for f in gt for o in f}):
            b,pid,_ = fixed_id_curve(gt,predictions["B0"],gid,category)
            a,_,_ = fixed_id_curve(gt,predictions["A0"],gid,category)
            key = (vid,gid)
            for t in range(5,len(gt)):
                if failure_label(b,t) != "persistent_failure":
                    continue
                stages[STAGES[0]].add(key)
                accepted = [e["frame"] for e in log[:t] for action in e["actions"]
                            if action.get("id")==pid and action["action"] in {"refresh","discover"}]
                if pid not in log[t-1]["active_ids"] or not accepted or t-max(accepted)>summary["configuration"]["sam_retention_steps"]:
                    continue
                stages[STAGES[1]].add(key)
                if not has_correct_run(a[:t-2]):
                    continue
                stages[STAGES[2]].add(key)
                row = inspect_event(gt,predictions,trace,log,summary["configuration"],
                                    {"video_id":vid,"gt_id":gid,"category":category,"frame":t})
                if not row["eligible_common_state"]:
                    continue
                if key not in stages[STAGES[3]]:
                    first_examples.append({"video_id":vid,"gt_id":gid,"first_shared_state_B_failure_step":t,
                                           "remaining_steps":len(gt)-t-1,"recent_B_iou":b[t-2:t+1]})
                stages[STAGES[3]].add(key)
                if t+30>=len(gt) or not all(any(o.identity==gid for o in gt[s]) for s in range(t,t+31)):
                    continue
                stages[STAGES[4]].add(key)
                if row["yolo_correction"] is not None:
                    stages[STAGES[5]].add(key)
        print("Coverage",vid,flush=True)
    result = {
        "status":"completed_read_only_native_B_coverage",
        "queue_sha256":digest(queue_path),"split_sha256":digest(split_path),
        "screened_videos":len(set(queue["video_ids"])-{2967}),
        "counts_distinct_video_GT_keys":{s:len(stages[s]) for s in STAGES},
        "keys":{s:[list(k) for k in sorted(stages[s])] for s in STAGES},
        "first_shared_state_examples":first_examples,
        "source_sha256":digest(Path(__file__)),
        "interpretation":"Nested observed eligibility at some native step. Not H/R results, not an unbiased failure frequency. Other video sources were not added to obtain failures.",
    }
    write_json(output,result)
    print(result["counts_distinct_video_GT_keys"],flush=True)
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ("queue","baselines","data-root","split","output"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args(argv)
    inspect_queue(a.queue,a.baselines,a.data_root,a.split,a.output)


if __name__=="__main__":
    main()
