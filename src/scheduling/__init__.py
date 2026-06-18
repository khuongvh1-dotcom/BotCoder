"""Scheduling (v0.3 stub): parallel execution support. The MVP runs tasks
sequentially in main.py and does not import these modules yet.

- worker_pool.py    — pool of workers running tasks concurrently
- scheduler.py      — pick runnable tasks per execution rules + risk
- dependency_graph.py — order tasks by depends_on
- lock_manager.py   — path-lock + conflict_group-lock to prevent collisions
"""
