# Can a reviewer answer a question about a change within two minutes?

This unrun pilot compares two ways to revise a pull request description. Two
human editors each revise 12 originals. Both receive the same instruction to
make the description easier to read and keep every fact. On half their tasks
they also receive readcost's questions. Four different people review the
edits. The primary outcome is **both keyed facts correct within 120 seconds**,
using the revised description and the full diff.

The materials contain no submitted edits, reviewer answers, scores or times.
The [edit-arms experiment](https://github.com/arclabs561/readcost/pull/96)
studies model editors and judges separately.

## Cases

Each entry in `cases.json` freezes the original PR description, the two Git
commits, the diff hash, the tool feedback, the reviewer question, the two
keyed facts and where to verify them in the diff. Cases A and B are the
previously prepared practice materials (#101 and #106). Use all 12 with
people who have not seen the practice packets or keys. Record familiarity
with the historical PRs before assigning participants. Keep anyone who
already saw a packet out of this cohort.

For the other ten, we examined closed PRs #107 through #7 in descending
order. We considered changes by `arclabs561` whose merge commits and
parents are in the history of
`5fb3a120eb8b76631e1dbbd1f9c720ffd706ee57`. We retained text diffs of at
most 1,500 added plus removed lines, with at least one question from the tool
and two facts we could verify in the diff. We set the size limit while
preparing the materials. Both code and changes to workflows or evaluation
reports qualified. Counts cited in an evaluation question refer to the
historical report in that diff.

The resulting PRs are #105, #97, #89, #83, #82, #80, #33, #25, #15 and #8.
The feedback is the stdout of `readcost check - -o agent --fail-on never` on
each frozen original at the commit above, with repository settings and
spaCy en_core_web_sm 3.8.0. This sample selects descriptions that triggered
feedback. It cannot estimate how often readcost would speak up on a new PR.

## Conduct the pilot

Keep this directory and the allocation private from participants. Run the
sessions offline. Give each participant only the current numbered task and
its diff, without access to the working directory, other packets or answer
keys. A full Git checkout with the frozen commits and Python 3 is enough to
generate packets. To rehearse with temporary placeholders, run
`python3 eval/human-pr-pilot/verify_packets.py`. For real sessions, use a
fresh private directory and run the following commands from the repository root.

1. Run `python3 eval/human-pr-pilot/packets.py editors /tmp/readcost-human-pilot`.
   It verifies all 12 diff hashes before writing tasks. Randomly assign the
   two editors to directories 1 and 2. Allow five minutes per task. They may
   keep the original. Save only the submitted description to its matching
   edit file, such as `editors/1/A.edit.txt`. Editors see their own guidance.
2. After all 24 edits arrive, run
   `python3 eval/human-pr-pilot/packets.py reviewers /tmp/readcost-human-pilot`.
   Randomly assign four other people to R1–R4. Follow the frozen order. Each
   reviewer sees every case once, six edits per arm and six per editor.
   Each edit appears twice across two reviewers, once before and once after
   the midpoint and once in each position within its pair. Every ordinal has two
   reviews per arm across the four schedules.
3. Reveal the question, description and diff together and start the clock.
   Stop when the reviewer submits a final written answer, or at 120 seconds.
   Accept submission at exactly the deadline. Record anonymous reviewer, task
   ordinal, elapsed seconds, timeout and verbatim answer. Allow breaks
   between pairs. Record interruptions and accidental previews separately.
   Keep the original assignments and document any missing trials.
4. Give a grader the case, question, key and anonymous answer. Conceal the
   editor, arm, time and reviewer. Require both facts and reject a
   contradiction. Lock the grades before joining them to times and arms.
   Separately compare each of the 24 anonymous revisions with its source and
   diff. Quote any lost fact, changed fact or unsupported addition. Record
   and report scoring disputes.

## Report

Each arm has 24 scheduled answers, two per case. A wrong, absent or late
answer scores zero. Report counts and denominators for correct answers within
120 seconds by arm and case. Give the numbers wrong, missing, timed out and
affected by protocol deviations. Show the elapsed times among correct
responses as a secondary outcome alongside the accuracy counts. Summarize
edit fidelity separately.

The 48 responses share cases, editors and reviewers. Some historical changes
also share workflows or evaluation data. Present the arm difference as a
description of this pilot. Four reviewers do not support treating all 48
responses as independent measurements of the population effect.
