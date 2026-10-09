"""One-to-one assignment with exclusions, a CSPRNG and full validation."""
import secrets
from functools import lru_cache


class ImpossibleDraw(ValueError):
    pass


def draw_assignment(participant_ids, forbidden_pairs):
    """Return {giver_id: receiver_id}; never return an invalid matching.

    Family groups of up to 16 participants are sampled uniformly across all
    valid complete matchings. Larger groups use randomized backtracking.
    """
    ids = list(participant_ids)
    if len(ids) < 3 or len(ids) != len(set(ids)):
        raise ImpossibleDraw('Mindestens drei unterschiedliche Teilnehmer sind erforderlich.')
    blocked = set(forbidden_pairs)
    choices = {g: [r for r in ids if r != g and (g, r) not in blocked] for g in ids}
    if any(not opts for opts in choices.values()):
        raise ImpossibleDraw('Mindestens eine Person hat keinen möglichen Empfänger.')
    # For family-size groups, count matching completions to sample every
    # admissible complete draw with equal probability (not just random search).
    if len(ids) <= 16:
        n = len(ids)
        options = [[j for j, receiver in enumerate(ids) if receiver in choices[giver]] for giver in ids]

        @lru_cache(maxsize=None)
        def count_completions(index, used):
            if index == n:
                return 1
            return sum(count_completions(index + 1, used | (1 << j))
                       for j in options[index] if not (used & (1 << j)))

        if count_completions(0, 0) == 0:
            raise ImpossibleDraw('Diese Ausschlüsse machen eine vollständige Auslosung unmöglich.')
        mapping = {}
        used = 0
        for index, giver in enumerate(ids):
            candidates = [(j, count_completions(index + 1, used | (1 << j)))
                          for j in options[index] if not (used & (1 << j))]
            pick = secrets.randbelow(sum(weight for _, weight in candidates))
            for j, weight in candidates:
                if pick < weight:
                    mapping[giver] = ids[j]
                    used |= (1 << j)
                    break
                pick -= weight
        return mapping

    # Larger groups: randomized backtracking. A valid draw is guaranteed;
    # uniform distribution over *all* valid matchings is not guaranteed.
    rng = secrets.SystemRandom()
    for opts in choices.values():
        rng.shuffle(opts)

    # Backtracking on most constrained giver, with pruning for impossible branches.
    def search(unassigned, available, answer):
        if not unassigned:
            return answer.copy()
        options_by_giver = {g: [r for r in choices[g] if r in available] for g in unassigned}
        if any(not o for o in options_by_giver.values()):
            return None
        if len(set().union(*[set(o) for o in options_by_giver.values()])) < len(unassigned):
            return None
        min_size = min(len(o) for o in options_by_giver.values())
        tied = [g for g in unassigned if len(options_by_giver[g]) == min_size]
        giver = rng.choice(tied)
        targets = list(options_by_giver[giver])
        rng.shuffle(targets)
        for recipient in targets:
            answer[giver] = recipient
            found = search([g for g in unassigned if g != giver], available - {recipient}, answer)
            if found is not None:
                return found
            del answer[giver]
        return None

    mapping = search(ids, set(ids), {})
    if mapping is None:
        raise ImpossibleDraw('Diese Ausschlüsse machen eine vollständige Auslosung unmöglich.')
    if (set(mapping) != set(ids) or set(mapping.values()) != set(ids)
            or any(g == r or (g, r) in blocked for g, r in mapping.items())):
        raise AssertionError('Interner Fehler bei der Auslosungsprüfung')
    return mapping
