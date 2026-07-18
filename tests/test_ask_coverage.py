from leaderlodge.insights.ask_coverage import analyze_ask_tool_coverage


def test_whole_roster_question_matches_men_and_women():
    coverage = analyze_ask_tool_coverage(
        tool_rounds=[],
        roster_player_count=10,
        question="Do men or women play better in dominos?",
    )
    assert coverage["likely_incomplete"] is True


def test_small_roster_skips_incomplete_warning():
    coverage = analyze_ask_tool_coverage(
        tool_rounds=[],
        roster_player_count=3,
        question="Do men or women play better?",
    )
    assert coverage["likely_incomplete"] is False
