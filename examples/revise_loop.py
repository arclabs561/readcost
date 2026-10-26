"""Use readcost inside your own agent loop: draft, check, revise once.

`generate(prompt) -> str` stands in for your model call.
"""

from readcost.hooks.generic import review


def answer(prompt: str, generate) -> str:
    draft = generate(prompt)
    verdict = review(draft)
    if verdict["verdict"] != "block":
        return draft
    # One revision round only: a second pass rarely helps and can loop.
    return generate(
        f"{prompt}\n\nYour draft:\n{draft}\n\n{verdict['feedback']}\n"
        "Return only the revised answer."
    )


if __name__ == "__main__":
    print(review("It does not own indexing, compaction, or reader visibility, "
                 "and it prints the first snapshot-search cost with persisted "
                 "region-index sidecars present.")["feedback"])
