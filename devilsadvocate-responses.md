---

### 2026-03-24 — googleplanner

**Reviewed:** OR-Tools CP-SAT resource planner — story point / velocity design and overall approach
**Verdict:** Technically sound skeleton; inputs are too soft to trust the output dates without honest calibration of velocity and acknowledgement of unknowns.

Alright. Here's my honest take.

**The velocity number is fiction.**

You've assigned Sarah a velocity of 1.5 pts/day as if that's a law of physics. It isn't. That number changes depending on whether she's on a complicated scheme she's never touched, whether she's got three meetings Thursday, whether the spec she was handed is actually complete. A single decimal point doesn't capture any of that. The whole schedule pivots on that number being right, and it won't be.

**You're just doing time estimation with extra steps.**

Story points exist precisely *because* converting them to time is unreliable. The formula `days = ceil(points / velocity)` is just `days = estimate` dressed up in different clothes. You haven't removed the estimation problem — you've hidden it inside the velocity setting and called it science. If you were going to estimate days, just estimate days. At least that's honest.

**The solver finds the optimal schedule for the model, not for reality.**

CP-SAT will tell you Sarah should start the DEF spec review on day 4 immediately after finishing the ABC spec. Lovely. Does Sarah know that? Has anyone told her? Does she have onboarding time for a scheme she's not worked on before? The model has no concept of ramp-up, context switching cost, or the fact that a developer hammering two schemes in parallel doesn't do either as well as one at a time.

**Your UAT tester is a 0.5-velocity ghost.**

"UAT Resource, velocity 0.5, TBC." The entire back end of your schedule depends on this person. You don't know who they are, you've guessed their throughput, and they'll be doing this on top of their day job. One wrong assumption here and your schedule end date is wrong by weeks, and the Gantt chart will look completely authoritative because it came out of an optimisation solver.

**The YAML will drift immediately.**

Week two of the project, someone changes the spec for SchemeABC and the tranche 2 points need updating. Who owns that update? Does it happen? Or does the plan just sit there looking correct while the actual work has moved on? I've seen this exact pattern with project tracking tools — they're maintained religiously for the first sprint and then abandoned. YAML is not a living document. It's a snapshot.

**The Fibonacci validation is a polite suggestion, not a constraint.**

You print a warning. That's it. Someone will type `points: 4` and you'll say "hey, that's not Fibonacci" and they'll think "whatever" and carry on. If the Fibonacci discipline matters — and it only matters if the team has actually calibrated velocity against those specific numbers — then either enforce it hard or don't bother.

**What it does get right**, since I'm being fair: the solver correctly won't double-book Sarah, it respects dependencies, and the faster developer genuinely does get preferred for complex work. That part is mathematically sound and it would catch scheduling mistakes a spreadsheet planner would miss.

But I'd be very cautious about presenting the output Gantt chart to a stakeholder as a delivery date. It's a model of a model, and the inputs are soft.
