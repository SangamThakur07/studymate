"""
create_study_plan() tool. Turns the current mastery profile + knowledge
graph prerequisites into an ordered list of what to study next.
"""
from app.services.llm_service import llm_service


def create_study_plan(profile: dict, prerequisite_graph: dict) -> list[dict]:
    """
    profile: output of get_student_profile()
    prerequisite_graph: {concept_name: [prerequisite_names]}

    Returns an ordered list of {concept, reason} the agent recommends
    studying next, weakest-and-most-foundational first.
    """
    weak_topics = profile.get("weak_topics", [])
    mastery = profile.get("mastery", {})

    plan = []
    for topic in weak_topics:
        prereqs = prerequisite_graph.get(topic, [])
        unmet_prereqs = [p for p in prereqs if mastery.get(p, 0) < 60]

        if unmet_prereqs:
            for p in unmet_prereqs:
                plan.append({
                    "concept": p,
                    "reason": f"Prerequisite for '{topic}', currently weak "
                              f"({mastery.get(p, 0)}%). Must fix before {topic} "
                              f"will make sense.",
                })
        else:
            plan.append({
                "concept": topic,
                "reason": f"Weak topic ({mastery.get(topic, 0)}%), prerequisites are solid.",
            })

    # de-duplicate while preserving order
    seen = set()
    ordered_plan = []
    for item in plan:
        if item["concept"] not in seen:
            seen.add(item["concept"])
            ordered_plan.append(item)

    return ordered_plan
