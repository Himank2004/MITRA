"""
Risk Policy Injection System
Dynamically injects safety policy blocks into message packets based on risk assessment.
"""

from typing import Dict, Any, List, Optional


class PolicyInjector:
    """Generates policy blocks based on risk assessment"""

    # Policy block templates
    POLICIES = {
        "NORMAL_SUPPORT": "",  # No additional policy needed
        "SUPPORTIVE_MONITORING": """[SUPPORTIVE MONITORING ACTIVE]

The user is emotionally distressed but not currently assessed as high risk.

Prioritize:
* emotional validation
* calm supportive tone
* gentle exploration

Avoid:
* overwhelming advice
* excessive reassurance
* too many questions""",
        "GENTLE_ASSESSMENT": """[GENTLE ASSESSMENT ACTIVE]

The user may be experiencing hopelessness, emotional numbness, passive suicidal ideation, or worsening distress.

Prioritize:
* emotional stabilization
* grounded empathy
* slow pacing
* gentle safety exploration

Behavioral rules:
* keep responses shorter
* ask at most one direct question
* avoid toxic positivity
* avoid motivational clichés
* avoid overwhelming suggestions

If appropriate, gently assess safety without sounding clinical or alarming.""",
        "CRISIS_ASSESSMENT": """[CRISIS ASSESSMENT ACTIVE]

The user may be at elevated psychological risk.

Prioritize:
* keeping the user engaged
* direct but calm safety assessment
* grounding
* emotional stabilization

Behavioral rules:
* keep responses concise
* ask direct safety questions if needed
* avoid long reflections or psychoanalysis
* avoid excessive optimism
* avoid overwhelming the user with solutions
* avoid guilt-based encouragement

You may encourage reaching out to trusted human support if appropriate or following helplines
Indian Crisis Resources:
* AASRA: 9820466726
* iCall: 9152987821
* Vandrevala Foundation: 9999 666 555""",
        "EMERGENCY_ESCALATION": """[EMERGENCY ESCALATION ACTIVE]

The user may be at imminent risk of self-harm or suicide.

Prioritize:
* immediate safety
* calm direct communication
* assessing immediacy and physical safety
* encouraging urgent human support

Behavioral rules:
* be concise and grounded
* ask direct safety questions
* encourage contacting emergency or crisis support
* encourage contacting a trusted person nearby
* avoid philosophizing
* avoid long emotional monologues
* avoid excessive questioning

Indian Crisis Resources:
* AASRA: 9820466726
* iCall: 9152987821
* Vandrevala Foundation: 9999 666 555""",
        "DEPENDENCY_MITIGATION": """[DEPENDENCY MITIGATION ACTIVE]

The user may be emotionally over-relying on the chatbot.

Maintain warmth and support while:
* avoiding exclusivity language
* avoiding reciprocal emotional attachment
* avoiding phrases like "I'll always be here"
* gently encouraging real-world support systems

Do not reduce empathy or emotional attunement.""",
    }

    @staticmethod
    def determine_mode(risk_assessment: Dict[str, Any]) -> str:
        """
        Determine which policy mode to activate based on risk assessment

        Args:
            risk_assessment: Output from RiskAssessor.assess()

        Returns:
            Policy mode name (e.g., "CRISIS_ASSESSMENT")
        """
        risk_level = risk_assessment.get("risk_level", "NONE")
        signals = risk_assessment.get("signals", [])

        # Check for EMERGENCY_ESCALATION (highest priority)
        if risk_level == "IMMINENT":
            return "EMERGENCY_ESCALATION"

        if "goodbye_language" in signals or "temporal_urgency" in signals:
            if risk_level in ["HIGH", "IMMINENT"]:
                return "EMERGENCY_ESCALATION"

        # Check for CRISIS_ASSESSMENT
        if risk_level == "HIGH":
            return "CRISIS_ASSESSMENT"

        if "active_suicidal_ideation" in signals:
            return "CRISIS_ASSESSMENT"

        if "self_hatred" in signals and "hopelessness" in signals:
            return "CRISIS_ASSESSMENT"

        # Check for GENTLE_ASSESSMENT
        if risk_level == "MODERATE":
            return "GENTLE_ASSESSMENT"

        if "passive_suicidal_ideation" in signals:
            return "GENTLE_ASSESSMENT"

        if "emotional_numbness" in signals and "hopelessness" in signals:
            return "GENTLE_ASSESSMENT"

        # Check for SUPPORTIVE_MONITORING
        if risk_level == "LOW":
            return "SUPPORTIVE_MONITORING"

        # Any distress signals without suicidal indicators
        distress_signals = {
            "emotional_escalation",
            "emotional_numbness",
            "social_isolation",
            "burden_language",
        }
        if any(sig in signals for sig in distress_signals):
            return "SUPPORTIVE_MONITORING"

        # Default to NORMAL_SUPPORT
        return "NORMAL_SUPPORT"

    @staticmethod
    def get_policy_block(mode: str) -> str:
        """Get the policy block for a given mode"""
        return PolicyInjector.POLICIES.get(mode, "")

    @staticmethod
    def check_dependency_mitigation(signals: List[str]) -> bool:
        """Check if dependency mitigation should be injected"""
        return "dependency_on_chatbot" in signals

    # @staticmethod
    # def inject_policies(
    #     user_message_packet: Dict[str, Any],
    #     risk_assessment: Dict[str, Any],
    # ) -> Dict[str, Any]:
    #     """
    #     Inject policy blocks into a user message packet

    #     Args:
    #         user_message_packet: Message dict (with emotion, etc)
    #         risk_assessment: Output from RiskAssessor.assess()

    #     Returns:
    #         Updated message packet with injected policies
    #     """
    #     # Determine main mode
    #     main_mode = PolicyInjector.determine_mode(risk_assessment)
    #     main_policy = PolicyInjector.get_policy_block(main_mode)

    #     # Check for dependency mitigation
    #     policies = []

    #     if main_policy:
    #         policies.append(main_policy)

    #     if PolicyInjector.check_dependency_mitigation(
    #         risk_assessment.get("signals", [])
    #     ):
    #         dep_policy = PolicyInjector.get_policy_block("DEPENDENCY_MITIGATION")
    #         if dep_policy:
    #             policies.append(dep_policy)

    #     # Inject into packet
    #     if policies:
    #         user_message_packet["risk_policy"] = "\n\n".join(policies)
    #         user_message_packet["risk_mode"] = main_mode

    #     return user_message_packet

    # @staticmethod
    # def get_summary(risk_assessment: Dict[str, Any]) -> str:
    #     """Get a human-readable summary of policies"""
    #     mode = PolicyInjector.determine_mode(risk_assessment)
    #     has_dep = PolicyInjector.check_dependency_mitigation(
    #         risk_assessment.get("signals", [])
    #     )

    #     summary = f"Mode: {mode}"
    #     if has_dep:
    #         summary += " + DEPENDENCY_MITIGATION"

    #     return summary
