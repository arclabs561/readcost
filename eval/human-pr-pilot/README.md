# Can a reviewer answer a question about a change within two minutes?

This is an unrun, two-PR starter for a human pilot. Editors revise a PR
description after either a generic instruction or the same instruction plus
readcost's questions. A different person then answers a question using the
revision and the frozen diff. The primary outcome is **both keyed facts
correct within 120 seconds**. A wrong, missing or late answer scores zero.

The separate [edit-arms experiment](https://github.com/arclabs561/readcost/pull/96)
studies model edits of documentation and uses model judges. This pilot uses
human editors and reviewers. The coordinator keeps the following materials
private from participants until all responses have been scored. Run the
sessions offline. Participants use only the assigned packet. Record prior
familiarity with either change before revealing the tasks.

## Prepare the packets

Run from the repository root with Python 3 and a checkout containing the two
merged commits in `cases.json` and their parents. Use a fresh private directory.

```sh
python3 eval/human-pr-pilot/packets.py editors /tmp/readcost-human-pilot
```

The script reproduces each full diff locally and checks its SHA-256 before
writing any packets. The two original descriptions come from merged PRs
[#101](https://github.com/arclabs561/readcost/pull/101) and
[#106](https://github.com/arclabs561/readcost/pull/106). Their frozen feedback
is the stdout of `readcost check - -o agent --fail-on never` on each original
at commit `5fb3a120eb8b76631e1dbbd1f9c720ffd706ee57`, with the repository
config and spaCy en_core_web_sm 3.8.0. Both were selected for having a
finding and a checkable answer. PR #104 produced no questions. This draw
cannot estimate how often ordinary PRs would get feedback.

## Conduct one block

1. Randomly assign two editors to directories 1 and 2. Give each editor only
   their own tasks, one at a time, in numbered order. Allow the same five
   minutes and diff access for each. They may keep the original unchanged.
   Save only their submitted text in the matching `A.edit.txt` or
   `B.edit.txt`. Keep the question and key in `cases.json` out of sight.
   Editors can see whether their own instructions contain feedback.
2. After all four edits are in, run
   `python3 eval/human-pr-pilot/packets.py reviewers /tmp/readcost-human-pilot`.
   Randomly assign four other people to R1–R4. Each receives one description
   per change, one generic edit and one question-guided edit. Each variant
   appears once first and once second. Keep editor identities, conditions,
   original drafts, keys and other reviewers' answers out of their packets.
3. Tell each reviewer they have two minutes per task and may consult the
   supplied diff. Reveal the numbered question, description and diff together
   and start a stopwatch. Stop when the reviewer submits a final written
   answer, or at 120 seconds. A timeout scores zero. Accept a completed submission
   at exactly the deadline.
   Record anonymous reviewer, task ordinal, elapsed seconds, timeout and
   verbatim answer. An interrupted or accidentally previewed trial is a
   protocol deviation. Record and report it separately. Never substitute
   another trial after seeing an answer.
4. Give a grader the case, question, key and anonymous answer, with editor,
   arm, time and reviewer concealed. Require both listed facts and reject a
   contradiction. Lock those scores before combining them with the stopwatch
   log and the arm allocation. Separately inspect the four anonymous edits
   against the original description and diff. List factual losses, changes
   or unsupported additions by quoting the affected claims; disclose any
   disagreement over scoring before interpreting a difference.

## Report

Give correct-within-deadline counts and denominators for each arm and each PR,
along with wrong answers, timeouts and deviations. Show elapsed times for
correct responses as a secondary outcome, alongside the accuracy counts;
conditioning on success can favor the arm with fewer correct answers.
Report edit fidelity separately. A description can earn a correct response
while changing a fact outside the keyed question.

Two PRs and four reviewers give four response opportunities per arm. Items,
editors and reviewers repeat. Use the eight observations to check packet
handling, timing and scoring. They cannot supply a population confidence
interval. For the proposed 12-PR, four-reviewer pilot, freeze the other ten
originals, diffs, questions, keys and assignments before collecting any
responses on those items. Keep pilot practice items separate if their answers
or the procedure change. No edits, human answers or timings are supplied here.
