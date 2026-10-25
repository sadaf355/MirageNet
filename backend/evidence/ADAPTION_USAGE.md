# Adaption SDK Usage & Verification

## 1. Verified Live Account State

Using the authenticated `ADAPTION_API_KEY`, MirageNet performed a direct, verified SDK query against the user's Adaption account:

- **Decoy Dataset ID**: `804c2643-496f-4951-9ff8-f7814c73071b`
- **Dataset Name**: `decoy_file_artifacts`
- **Status**: `succeeded`
- **Total Rows**: `499`
- **Evaluation Status**: `completed`
- **Dataset Quality**: Grade **A** (`score_before: 9.0`, `score_after: 9.0`, `percentile_after: 33.0`)
- **Inspection Script**: `backend/scripts/run_adaption_live.py --read-only 804c2643-496f-4951-9ff8-f7814c73071b` (verified with 0 extra credits spent).

## 2. Blocked / Pending Live Generation Steps

When executing new generation calls (`client.datasets.invent()`):
- **Error Returned**: `402 Payment Required` (account has exhausted active generation credits).
- **Status in Manifest**: `"session_dataset_status": "not_run_out_of_credits"`
- **Manifest Note**: `"not run: out of credits (Adaption API returned 402 Payment Required for new invent jobs)"`

### Pending Steps to Complete When Credits Are Available:
1. **Live Decoy Generation**: Run `python scripts/run_adaption_live.py --live` with `ADAPTION_API_KEY` to run fresh `datasets.invent()` on `brief.txt` (200 rows).
2. **Session Trajectories Invent**: Run `client.datasets.invent()` on `data/adaption_evidence/session_brief.txt` (30 rows).
3. **Session Trajectory Evaluation**: Call `client.datasets.get_evaluation()` on the resulting session trajectory dataset.

## 3. Operational Mode

- **Decoy Lab & Simulation**: Running in reproducible `"cache"` mode with transparent labeling (`cache_rubric` per-row scoring).
- **Evidence Bundle**: Manifest records both the verified dataset `804c2643-496f-4951-9ff8-f7814c73071b` and the honest `not run: out of credits` state for pending generation jobs.
