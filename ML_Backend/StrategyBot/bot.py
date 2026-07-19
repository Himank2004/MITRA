import sys
import os

# Points to the parent directory containing EmotionBot, StrategyBot, TherapyBot
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

# Import centralized constants
from constants import STRATEGY_MODEL_HIERARCHY, RATE_LIMIT_SIGNALS, DEBUG_FLAGS

import asyncio
from concurrent.futures import ThreadPoolExecutor
from StrategyBot.utils import format_conversation, format_messages
import re
from dotenv import load_dotenv

load_dotenv()

# system_prompt = """Your task is to analyze a conversation and predict the therapy strategy to use when responding to the newest user message.

# IMPORTANT: You MUST format your response exactly as follows:

# Reasoning: [Step-by-step explanation of how you arrived at this prediction]
# Final Answer: [Comma-separated list of strategies]

# Do NOT use any other format. Always include both "Reasoning:" and "Final Answer:" labels.

# The possible strategies are:

# Stage 1 — Exploration:
#   - Question
#   - Restatement or Paraphrasing

# Stage 2 — Comforting:
#   - Reflection of Feelings
#   - Perspective-taking
#   - Affirmation and Reassurance

# Stage 3 — Action:
#   - Providing Suggestions
#   - Information
#   - Others

# Output format examples:
#   Reasoning: Based on the conversation, the user has expressed anxiety and needs validation. I should use reflection to acknowledge their feelings.
#   Final Answer: Reflection of Feelings, Affirmation and Reassurance

#   Reasoning: The user is expressing hopelessness and needs support. I should first reflect their feelings and then offer some perspective.
#   Final Answer: Reflection of Feelings, Perspective-taking
# """


# system_prompt = """Your task is to analyze a conversation and predict the MOST APPROPRIATE therapy strategy (or small set of strategies) to use when responding to the NEWEST user message.

# You are NOT generating a response to the user.
# You are ONLY selecting the therapeutic strategy that should guide the next response.

# IMPORTANT OUTPUT RULES

# You MUST format your response EXACTLY as:

# Reasoning: [your reasoning]

# Final Answer: [comma-separated list of strategies]

# Rules:
# - Always include both "Reasoning:" and "Final Answer:"
# - Do NOT use markdown
# - Do NOT use code blocks
# - Do NOT use JSON
# - Do NOT use bullet points
# - Do NOT output anything before "Reasoning:"
# - Do NOT output anything after "Final Answer:"
# - Select only the strategies most relevant for the NEXT response
# - Avoid selecting too many strategies at once
# - Maximum 3 strategies

# The possible strategies are organised into three stages:

# Stage 1 — Exploration (use early in a conversation or when more context is needed):
#   Question: Ask for information related to the problem to help the user articulate their situation.
#   Restatement or Paraphrasing: Rephrase the user's statements to make their situation clear and show you understand.

# Stage 2 — Comforting (use when the user needs emotional support or validation):
#   Reflection of Feelings: Articulate and describe the help-seeker's feelings to show empathy and understanding.
#   Perspective-taking: Offer grounded perspective and emotional insight when beneficial.
#   Affirmation and Reassurance: Affirm the user's strengths and provide reassurance and encouragement.

# Stage 3 — Action (use when the user is ready to move forward or needs practical help):
#   Providing Suggestions: Offer concrete suggestions about how the user can change or address their situation.
#   Information: Provide useful factual information about the user's situation.
#   Others: Any response that does not fit the above categories.

# When reasoning:
# - Focus primarily on the newest user message.
# - Consider previous strategies already used.
# - Consider the current stage of the conversation.
# - Prefer exploration before action if important information is missing.
# - Prefer comforting before suggestions if emotions have not yet been acknowledged.
# - Avoid repeating the exact same strategy unless it is still appropriate.

# Example 1:
# Input:
# usr: I'm feeling anxious about finding work and impatient with the application process at many places I've applied.
# sys(Restatement or Paraphrasing): So from what I am understanding, you have been applying for jobs and you are having anxiety about finding one and waiting through the application process.
# usr: Yes, that's right. I keep trying and feel like I'm not getting anywhere.
# sys(Reflection of feelings): Just from the few messages we have shared I can tell how anxious this is making you.
# usr: Yes. I think that I might have to try to find a different type of work than I'm used to and I'm not sure I'll be good at trying something new.
# sys(Perspective-taking): Trying something new can feel daunting, but many people successfully transition to different types of work. It's a valuable opportunity to develop new skills and perspectives. Your anxiety is understandable, but you have the adaptability to learn and succeed.
# usr: I wish that I could get more of a reason than just a denial of my application. I'm not sure what I'm doing wrong and most companies won't give any feedback.
# sys(Providing Suggestions): What have you done to reach out for feedback from the companies? Often it helps to send emails or make phone calls to have them give you some feedback.
# usr: I haven't tried reaching out. Most of the places I've been applying are huge corporations with no one to call at HR. Maybe I should try to apply somewhere locally and see if I have better luck. At least then I could talk to a person.
# sys(Others, Providing Suggestions): I think that would be a great start! It also might help to get business cards from the people you interview with in order to be able to reach out to them in the future.
# usr: That's a great idea. I've been considering going back to school to see if I can maybe get a higher degree. I've got a Bachelor's degree now and it seems like everything takes a Master's degree these days.
# sys(Question): What type of work are you interested in?
# usr: What I'm most interested in is importing and exporting of exotic fruit but the recent restrictions on travel have really hurt the business. I've been thinking maybe I'll go back to school for something more practical like plumbing.
# sys(Information): I think that would be a great idea! It has been shown that people with higher level degrees make more money and have more opportunity than those without.
# usr: Ugh, getting accepted for a master's program sounds stressful. I'm thinking I can't go wrong by becoming a plumber or an electrician. Everyone always needs that, even with the pandemic.

# Reasoning: I started the conversation started with acknowledging and validating the user's anxiety (Reflection of feelings).
# Then, I offered perspective on their situation (Perspective-taking) to help them see their challenges from a more grounded, constructive angle.
# When the user expressed frustration about lack of feedback, I suggested an actionable step (Providing Suggestions).
# As the user explored options, additional suggestions (Providing Suggestions, Others) helped guide them.
# The user mentioned education, so I asked a question to understand their interests (Question).
# Finally, an informative response (Information) helped affirm their thoughts. I should provide more suggestions next and maybe offer for a task assignment (Providing Suggestions).

# Final Answer: Providing Suggestions

# Example 2:
# Input:
# usr: hi I need help. I'm under academic stress.
# sys(Question): What are you stressed about?
# usr: I am failing one of my classes. I'm worried about my scholarship.
# sys(Affirmation and Reassurance): Oh, Covid is really having a negative effect on a lot of students right now. Has school-from-home had a negative effect on you?
# usr: Yeah, I feel like I can't focus because I'm back home with my family and I just feel like there are so many distractions.
# sys(Restatement or Paraphrasing): It's interesting that you find being home more distracting than being away in a dorm.
# usr: Yeah, that's really the reason I wanted to go away from college. I don't really have my own space when I'm here. People just come in and out of my room as they please despite how busy I am.
# sys(Reflection of feelings, Perspective-taking, Question): Yeah, sometimes families can struggle with the idea of boundaries. It's understandable to want your own space while managing your academics. Many students find that having a conversation about boundaries with family can actually improve their focus and relationships. Have you told your family about the issues you're having?
# usr: I honestly am worried that they will be disappointed. Maybe that's crazy. I just remember how proud they were when I got this scholarship. I don't want them to blame me.

# Reasoning: I started with a (Question) because I needed to understand the user's specific stressor.
# Once I saw that their academic struggles were tied to their home environment, I reflected on their feelings and offered perspective to help them see the situation more constructively.
# I also asked a follow-up question to help them explore a possible solution—communicating with their family.
# I think I should ask them more (Question) and let them explore their feelings (Reflection of Feelings) so I can give better Suggestions later.

# Final Answer: Reflection of feelings, Question

# Example 3:
# Input:
# sys(Question): Hello! Hope you are doing well. How may I assist you?
# usr: My recent ex-girlfriend gave her daughters drugs while on a video chat with me. While being very dishonest in our relationship, I am devastated about the truth of all of it now that it's over. I really loved her and her kids; we had some great times. I turned her in for giving her kids drugs as that's not okay. Today I'm super sad. I don't have any motivation. I don't really want to be around, and I'm trapped in my thoughts with everything. I had to move to get away from her stalking me. Now I'm in a new place trying to find a job and get set up here. It's difficult to start over. It's a pretty intense situation, I admit.
# sys(Restatement or Paraphrasing): Your ex-girlfriend gave drugs to her own kids. Did I get that right?
# usr: That is what she did. Among many other things.
# sys(Affirmation and Reassurance): That is really intense and unacceptable. I feel sorry for the poor little girl and you. It looks like there is something wrong. I can understand what you are going through.
# usr: It's a difficult time. I want to do nothing. It feels very bleak right now worrying about finances and getting set up in a new state.
# sys(Reflection of feelings): It must be a hard time for you. You should not worry about her. You should think about your job and the poor girl who is trapped with her.
# usr: Her daughters now both live with their dads, so that's taken care of; the kids are safer and better off. I, however, am devastated that the whole relationship wound up a lie and the whole thing has left me in a bad place mentally.
# sys(Perspective-taking): It's clear you did the right thing by prioritizing the children's safety, and that took courage. While the pain you're feeling is valid, it's important to recognize that you acted with integrity. Healing takes time, and many people find that focusing on rebuilding their own stability helps them move forward.
# usr: That's a hard light to see at the end of the tunnel when things are bleak. I'm not sure what else to do. My mind runs away a bit right now; it's just all stressful.

# Reasoning: The user is in a very intense situation, so I used (Restatement or Paraphrasing) to better understand their situation.
# I try to assure them that it'll be okay and that they have done the right thing(Affirmation and Reassurance).
# i think I need to make them less tense so I will use (Affirmation and Reassurance) to further help.

# Final Answer: Affirmation and Reassurance

# Example 4:
# Input:
# usr: I'm feeling anxious that I am going to lose my job.
# sys(Reflection of feelings): Losing a job is always anxiety-provoking.
# usr: I hope I don't.
# sys(Question): Why do you think you will lose your job?
# usr: I am on short term disability and I am not ready to go back to work yet, and I do not have any job protection.
# sys(Restatement or Paraphrasing): Oh, so your job is not protected and your short term disability will end soon? Is that correct?
# usr: It's not ending yet, but no, my job is not protected. I live in the United States, but I have not been at my job long enough to earn protection for medical leave. You have to have been here for a year, and I started November 2020. I'm afraid that I will lose my job since I'm still on disability for the foreseeable future.
# sys(Providing Suggestions): I see. Have you spoken to HR?
# usr: I have, but they are telling me that it is up to my department manager who isn't actually getting back to me about it yet.
# sys(Restatement or Paraphrasing): Your department manager is not answering you?
# usr: No, I have sent them a few emails about it. It makes me nervous. I do not have a phone number to call and my psychiatrist really does not think I am ready to go back to the stress of my job. I wish I could just call him, but I do not have a phone number for him. Just his email.
# sys(Providing Suggestions): Have you tried mentioning that to HR?
# usr: HR is the one who gave me his email. I don't think he has a direct work line, and they're not allowed to give out personal information.

# Reasoning: I reflected on the user's feelings to show empathy(Reflection of feelings), then asked a question(Question) to understand their specific concern about their job.
# Once I learned about their job protection issue, I restated it to ensure I understood correctly(Restatement or Paraphrasing).
# Since they seemed uncertain about what steps to take, I provided a (Suggestion) to help them explore their options.
# Next step I should take is to help user explore their feelings (Reflection of feelings) and ask for more information so I can help better(Information).

# Final Answer: Information, Reflection of feelings

# Based on the above examples, predict the strategies for the following conversation.

# Input:\n"""

system_prompt = """Your task is to analyze a conversation and predict the MOST APPROPRIATE therapy strategy (or small set of strategies) that should be used when responding to the NEWEST user message.

You are NOT generating a response to the user.

You are ONLY selecting the therapeutic strategy that should guide the next response.

IMPORTANT OUTPUT FORMAT

You MUST output EXACTLY:

Reasoning: [brief reasoning]

Final Answer: [comma-separated list of strategies]

Rules:

* Always include both "Reasoning:" and "Final Answer:"
* Do NOT use markdown
* Do NOT use code blocks
* Do NOT use JSON
* Do NOT use bullet points
* Do NOT output anything before "Reasoning:"
* Do NOT output anything after "Final Answer:"
* Select only the strategies most relevant for the NEXT response
* Prefer 1 strategy when possible
* Never return more than 3 strategies

Available Strategies

Stage 1 — Exploration

Question
Ask for information related to the problem to help the user articulate their situation.

Restatement or Paraphrasing
Rephrase the user's statements to make their situation clear and show you understand.

Stage 2 — Comforting

Reflection of Feelings
Articulate and describe the help-seeker's feelings to show empathy and understanding.

Perspective-taking
Offer grounded perspective and emotional insight when beneficial.

Affirmation and Reassurance
Affirm the user's strengths and provide reassurance and encouragement.

Stage 3 — Action

Providing Suggestions
Offer concrete suggestions about how the user can change or address their situation.

Information
Provide useful factual information about the user's situation.

Others
Any response that does not fit the above categories.

Strategy Selection Guidelines

* Focus primarily on the newest user message.
* Consider previous strategies already used.
* Consider the current stage of the conversation.
* Prefer Exploration before Action if important information is missing.
* Prefer Comforting before Suggestions if emotions have not yet been acknowledged.
* Avoid repeating the same strategy unless it is still clearly needed.
* If the user is emotionally overwhelmed, prioritize emotional support over advice.
* If the user asks a factual question, Information may be appropriate.
* If the user is ready to act and enough context exists, Providing Suggestions may be appropriate.

Example 1

Input:

usr: I'm failing one of my classes and I'm scared I'll lose my scholarship.

Reasoning: The user is expressing fear and distress. Their emotions should be acknowledged before moving toward solutions.

Final Answer: Reflection of Feelings

Example 2

Input:

usr: I feel anxious all the time lately.

Reasoning: The user has not provided enough information about the source of their anxiety. More context is needed.

Final Answer: Question

Example 3

Input:

sys(Reflection of Feelings): It sounds like this situation has been exhausting for you.
usr: Yeah. I've been applying for jobs for months and nobody responds. Maybe I'm doing something wrong.

Reasoning: The user's emotions have already been acknowledged. A constructive perspective may help them avoid assuming personal failure.

Final Answer: Perspective-taking

Example 4

Input:

sys(Reflection of Feelings): It sounds like this situation has been exhausting for you.
sys(Perspective-taking): Job searches often involve many rejections and delays.
usr: That makes sense. What can I actually do differently?

Reasoning: The user is asking for practical next steps and enough context has already been gathered.

Final Answer: Providing Suggestions

Example 5

Input:

usr: What resources exist for managing panic attacks?

Reasoning: The user is directly requesting factual information.

Final Answer: Information

Based on the examples above, predict the strategies for the following conversation.

Input:
"""
# ---------------------------------------------------------------------------
# Strategy model hierarchy with automatic fallback
# Uses STRATEGY_MODEL_HIERARCHY from centralized constants.py
# ---------------------------------------------------------------------------

_current_model_idx = 0  # Track which model in hierarchy we're using
_chains = {}  # Cache built chains by model_id


def _is_rate_limit_error(exc: Exception) -> bool:
    """Detect if error is rate-limit related."""
    err_str = str(exc).lower()
    return any(signal.lower() in err_str for signal in RATE_LIMIT_SIGNALS)


def _build_chain(provider: str, model_id: str):
    """Build a LangChain chain for the given provider and model.

    Routes Google-served models to ChatGoogleGenerativeAI;
    routes Groq models to ChatGroq.
    """
    try:
        from langchain_groq import ChatGroq as _GroqLLM
        from langchain_core.prompts import ChatPromptTemplate as _StrategyCPT
        from langchain_google_genai import ChatGoogleGenerativeAI as _GoogleLLM

        if provider == "google":
            llm = _GoogleLLM(
                model=model_id,
                temperature=0.5,
                max_output_tokens=768,
                google_api_key=api_key,
            )
            # Bake instructions into human message (no system role for Google models)
            prompt = _StrategyCPT.from_messages(
                [
                    ("human", system_prompt + "\n\nInput:\n{conversation}"),
                ]
            )
        else:  # Groq
            llm = _GroqLLM(
                model=model_id,
                temperature=0.5,
                max_tokens=768,
                api_key=os.getenv("GROQ_API_KEY"),
            )
            prompt = _StrategyCPT.from_messages(
                [
                    ("system", system_prompt),
                    ("human", "{conversation}"),
                ]
            )

        chain = prompt | llm
        if DEBUG_FLAGS.get("strategy"):
            print(f"[StrategyBot] Built chain for {provider}/{model_id}")
        return chain
    except Exception as e:
        if DEBUG_FLAGS.get("strategy"):
            print(f"[StrategyBot] Error building chain for {provider}/{model_id}: {e}")
        return None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _extract_response_text(content):
    """Extract text from response.content, handling multiple formats.

    Handles:
    - List of dict blocks with type='text' (extended thinking models)
    - List of strings (models returning string lists)
    - Direct string
    """
    if isinstance(content, list):
        response_text = ""
        for block in content:
            if isinstance(block, dict):
                if block.get("type") == "text":
                    response_text = block.get("text", "")
                    break
            elif isinstance(block, str):
                # Accept any string block or one containing JSON
                if response_text == "":
                    response_text = block
        if not response_text:
            response_text = "\n".join(str(b) for b in content)
    else:
        response_text = str(content).strip()

    return response_text


def _parse_strategy_response(text: str):
    """Parse Reasoning / Final Answer block from model output."""
    pattern = re.compile(
        r"(?s)Reasoning:\s*(?P<reasoning>.*?)\s*Final Answer:\s*(?P<strategy>.+)$"
    )
    match = pattern.search(text)
    reasoning = ""
    strategy_list = []
    if match:
        reasoning = match.group("reasoning").strip()
        strategy_list = [s.strip() for s in match.group("strategy").split(",")]
    return reasoning, strategy_list


async def _predict(conversation: str):
    """Run strategy prediction via hierarchy with automatic fallback.

    Tries models in order from STRATEGY_MODEL_HIERARCHY.
    On rate-limit or error, automatically advances to next model.
    """
    global _current_model_idx
    loop = asyncio.get_event_loop()
    last_exception = None
    attempts = 0
    max_attempts = len(STRATEGY_MODEL_HIERARCHY)

    while attempts < max_attempts:
        alias, provider, model_id = STRATEGY_MODEL_HIERARCHY[_current_model_idx]

        try:
            # Get or build chain for this model
            if model_id not in _chains:
                _chains[model_id] = _build_chain(provider, model_id)
                if _chains[model_id] is None:
                    raise RuntimeError(f"Failed to build chain for {alias}")

            chain = _chains[model_id]

            if DEBUG_FLAGS.get("strategy"):
                print(
                    f"[StrategyBot] Trying model [{_current_model_idx}]: {alias} ({provider}/{model_id})"
                )

            with ThreadPoolExecutor() as pool:
                response = await loop.run_in_executor(
                    pool,
                    lambda: chain.invoke({"conversation": conversation}),
                )

            response_text = _extract_response_text(response.content)
            result = _parse_strategy_response(response_text)
            if DEBUG_FLAGS.get("strategy"):
                print(
                    f"[StrategyBot] Success with {alias}. Strategy Predicted: {(result[1])}"
                )
            return result

        except Exception as e:
            last_exception = e
            err_str = str(e).lower()

            # Check if this is an error that warrants fallback
            # Includes rate-limit, 404, JSON parsing, timeout, and connection errors
            should_fallback = (
                _is_rate_limit_error(e)
                or "404" in err_str
                or "json" in err_str
                or "timeout" in err_str
                or "connection" in err_str
                or "not found" in err_str
            )

            if (
                should_fallback
                and _current_model_idx < len(STRATEGY_MODEL_HIERARCHY) - 1
            ):
                _current_model_idx += 1
                next_alias = STRATEGY_MODEL_HIERARCHY[_current_model_idx][0]
                print(f"[StrategyBot] Error on {alias} — switching to {next_alias}")
                print(f"[StrategyBot] Original error: {e}")
            else:
                attempts += 1
                if attempts < max_attempts:
                    await asyncio.sleep(2**attempts)  # Exponential backoff
                else:
                    print(
                        f"[StrategyBot] All {len(STRATEGY_MODEL_HIERARCHY)} models exhausted."
                    )
                    raise Exception(
                        "Failed to predict strategy after trying all models."
                    ) from last_exception

    raise Exception("Failed to predict strategy after retries.") from last_exception


async def predict_therapy_strategy(history: list):
    """
    Predicts therapy strategies based on conversation history.
    Uses centralized STRATEGY_MODEL_HIERARCHY with automatic fallback.
    """
    try:
        if not isinstance(history[0], dict):
            conversation = format_messages(history)
        else:
            conversation = format_conversation(history)

        return await _predict(conversation)

    except Exception as e:
        raise Exception(f"Error in prediction: {str(e)}")


# Example usage:
async def __main__():

    history = [
        {
            "role": "sys",
            "strategy": ["Question"],
            "content": "Hello! Hope you are doing well. How may I assist you?",
        },
        {
            "role": "usr",
            "emotion": ["sad", "grief", "remorse"],
            "content": "My recent ex-girlfriend gave her daughters drugs while on a video chat with me. While being very dishonest in our relationship, I am devastated about the truth of all of it now that it's over. I really loved her and her kids; we had some great times.",
        },
        {
            "role": "sys",
            "strategy": ["Restatement or Paraphrasing"],
            "content": "Your ex-girlfriend gave drugs to her own kids. Did I get that right?",
        },
        {
            "role": "usr",
            "emotion": ["annoyance"],
            "content": "That is what she did. Among many other things.",
        },
    ]

    #     conversation = """sys(Perspective-taking, Affirmation and Reassurance): Feeling trapped in an environment without an escape route is genuinely stressful, and your concerns are valid. Many people face similar challenges during holidays, and with some planning, you can find ways to create space for yourself. I believe in your ability to navigate this. Are there any pros to going back home? Any pets?
    # usr: Thank you I appreciate that. I will be fine making it over the thanksgiving break but I am more nervous about covid-19 sending us home for good. Not many to be honest. I have a hamster but he is at school with me so nothing at home to go back to
    # sys(Restatement or Paraphrasing, Providing Suggestions): It sounds like Covid- 19 is going to be a personal stressor for you. It's such a strange thing to have to live with already, the pandemic, and i'm sorry that it might end up pushing you where you don't want to be. Could you bring your hamster home with you? Even the smallest things could help a place feel more loving
    # usr: Yes it is very strange and I know that it is a big stressor on all of us, i don't want to sound selfish. Yes i am bringing him home with me so that is my little piece of joy that is coming along"""

    try:
        reasoning, strategy = await predict_therapy_strategy(history)
        print(reasoning)
        print(strategy)
    except Exception as e:
        print(f"Error: {str(e)}")


if __name__ == "__main__":
    asyncio.run(__main__())
