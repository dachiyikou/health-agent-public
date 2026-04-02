from health_agent.tools.parser import InputParser


def test_parser_recognizes_traditional_health_expression():
    parser = InputParser()
    parsed = parser.parse("我今天頭疼，身體不適怎麼辦")
    assert parsed["intent"] == "symptom_check"


def test_parser_uses_llm_classifier_when_rule_is_uncertain():
    parser = InputParser(intent_classifier=lambda text: "symptom_check")
    parsed = parser.parse("最近总觉得没精神")
    assert parsed["intent"] == "symptom_check"


def test_parser_maps_non_health_to_general_chat():
    parser = InputParser(intent_classifier=lambda text: "non_health")
    parsed = parser.parse("帮我写个旅游攻略")
    assert parsed["intent"] == "general_chat"


def test_parser_falls_back_for_invalid_classifier_label():
    parser = InputParser(intent_classifier=lambda text: "unknown_label")
    parsed = parser.parse("今天怎么样")
    assert parsed["intent"] == "general_chat"
