# UDA-Bench NBA data

The input of the NBA experiments, copied from UDA-Bench (https://github.com/BIT-DataLab/Bench-U, MIT License,
Copyright (c) 2025 DB-121), so that every system can be rebuilt on exactly the same documents:

- `docs/`: the 216 English Wikipedia articles of UDA-Bench's NBA ("Player") dataset, in the layout that
  `workspace-x6-s4/document_collections.json` reads: `player/player/` (141 players), `team/team/` (30 teams),
  `city/city/` (29 host cities) and `owner/owner/` (16 team owners). The articles are from Wikipedia (CC BY-SA).
- `ground_truth/Player/`: the gold tables and attribute descriptions, identical to `Query/Player/` of UDA-Bench at
  commit f2da981 (the copy every system is scored against).
