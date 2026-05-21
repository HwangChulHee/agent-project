"""차라투스트라 평가용 쿼리 셋 + 정답 라벨."""
from dataclasses import dataclass


@dataclass(frozen=True)
class NietzscheQuery:
    text: str
    lang: str                # "en" | "ko"
    category: str            # "factoid" | "concept" | "metaphor"
    answer_chapter: str      # 정답이 있는 chapter 헤더 (보조 시그널)
    answer_concept: str      # judge에 ground truth로 전달할 한 줄 요약


QUERIES = [
    # ==== Factoid (사실 기반) — 답이 한 leaf에 응집 예상 ====
    # EN
    NietzscheQuery(
        text="How old was Zarathustra when he left his home?",
        lang="en", category="factoid",
        answer_chapter="## Prologue",
        answer_concept="Zarathustra was 30 years old when he left his home for the mountains, and spent 10 years there before descending.",
    ),
    NietzscheQuery(
        text="What animals accompany Zarathustra?",
        lang="en", category="factoid",
        answer_chapter="## Prologue",
        answer_concept="An eagle and a serpent are Zarathustra's animal companions, representing pride and wisdom respectively.",
    ),
    NietzscheQuery(
        text="What does the saint in the forest do?",
        lang="en", category="factoid",
        answer_chapter="## Prologue",
        answer_concept="The old saint in the forest composes hymns and praises God; Zarathustra leaves him without revealing that 'God is dead'.",
    ),
    NietzscheQuery(
        text="What is the camel transformed into in 'The Three Metamorphoses'?",
        lang="en", category="factoid",
        answer_chapter="## I. The Three Metamorphoses",
        answer_concept="The camel transforms into a lion, then the lion into a child — three stages of spiritual transformation.",
    ),

    # KO
    NietzscheQuery(
        text="차라투스트라는 몇 살에 산으로 들어갔는가?",
        lang="ko", category="factoid",
        answer_chapter="## Prologue",
        answer_concept="차라투스트라는 서른 살에 고향과 호수를 떠나 산으로 들어가 십 년을 보냈다.",
    ),
    NietzscheQuery(
        text="차라투스트라와 함께하는 동물은?",
        lang="ko", category="factoid",
        answer_chapter="## Prologue",
        answer_concept="독수리와 뱀이 차라투스트라의 동반자. 독수리는 긍지, 뱀은 지혜를 상징.",
    ),
    NietzscheQuery(
        text="숲의 성자는 무엇을 하고 있는가?",
        lang="ko", category="factoid",
        answer_chapter="## Prologue",
        answer_concept="숲의 늙은 성자는 찬가를 지어 신을 찬양함. 차라투스트라는 '신은 죽었다'는 말을 그에게 알리지 않고 떠남.",
    ),
    NietzscheQuery(
        text="정신의 세 가지 변화에서 낙타는 무엇으로 변하는가?",
        lang="ko", category="factoid",
        answer_chapter="## I. 정신의 세 가지 변화",
        answer_concept="낙타가 사자로, 사자가 다시 어린아이로 변하는 세 단계의 정신적 변화.",
    ),

    # ==== Concept (개념/사상) — 큰 맥락 유리 예상 ====
    # EN
    NietzscheQuery(
        text="What is the Übermensch?",
        lang="en", category="concept",
        answer_chapter="## Prologue",
        answer_concept="The Superman/Übermensch is the goal humanity should strive for — a being who creates new values and overcomes the current human.",
    ),
    NietzscheQuery(
        text="What does Zarathustra teach about the last man?",
        lang="en", category="concept",
        answer_chapter="## Prologue",
        answer_concept="The last man is the contemptible figure who seeks only comfort and happiness, having lost all aspiration; opposite of the Übermensch.",
    ),
    NietzscheQuery(
        text="What is the doctrine of eternal recurrence?",
        lang="en", category="concept",
        answer_chapter="## XLVI. The Vision And The Enigma",
        answer_concept="Eternal recurrence: the idea that all events repeat infinitely. Tested as the heaviest weight on one's affirmation of life.",
    ),
    NietzscheQuery(
        text="What does 'God is dead' mean in Zarathustra's teaching?",
        lang="en", category="concept",
        answer_chapter="## Prologue",
        answer_concept="The death of God means the collapse of metaphysical absolutes; humanity must now create its own values without divine grounding.",
    ),

    # KO
    NietzscheQuery(
        text="초인이란 무엇인가?",
        lang="ko", category="concept",
        answer_chapter="## Prologue",
        answer_concept="초인(Übermensch)은 인간이 극복해야 할 목표. 기존 가치를 넘어 새로운 가치를 창조하는 존재.",
    ),
    NietzscheQuery(
        text="종말인(마지막 인간)에 대한 차라투스트라의 가르침은?",
        lang="ko", category="concept",
        answer_chapter="## Prologue",
        answer_concept="종말인은 안락과 행복만을 추구하며 동경을 잃은 경멸스러운 존재. 초인의 반대 형상.",
    ),
    NietzscheQuery(
        text="영원회귀 사상이란?",
        lang="ko", category="concept",
        answer_chapter="## XLVI. 환영과 수수께끼",
        answer_concept="모든 사건이 영원히 반복된다는 사상. 삶에 대한 긍정을 시험하는 '가장 무거운 짐'.",
    ),
    NietzscheQuery(
        text="'신은 죽었다'의 의미는?",
        lang="ko", category="concept",
        answer_chapter="## Prologue",
        answer_concept="신의 죽음은 형이상학적 절대성의 붕괴. 인간은 이제 신적 근거 없이 스스로 가치를 창조해야 함.",
    ),

    # ==== Metaphor (상징/은유) — 가장 어려움 예상 ====
    # EN
    NietzscheQuery(
        text="What does the tightrope walker symbolize?",
        lang="en", category="metaphor",
        answer_chapter="## Prologue",
        answer_concept="The tightrope walker represents humanity itself — a rope stretched between beast and Übermensch, with the act of crossing being more important than the destination.",
    ),
    NietzscheQuery(
        text="What is the meaning of 'going under' or 'down-going'?",
        lang="en", category="metaphor",
        answer_chapter="## Prologue",
        answer_concept="Going under (Untergang) is Zarathustra's descent from the mountain — a willing sacrifice/transition, a precondition for overcoming and creation.",
    ),
    NietzscheQuery(
        text="What does the spirit of gravity represent?",
        lang="en", category="metaphor",
        answer_chapter="## LV. The Spirit Of Gravity",
        answer_concept="The spirit of gravity is the demon of seriousness, conventional morality, and self-contempt — the enemy of light feet and joyful creation.",
    ),
    NietzscheQuery(
        text="What is the significance of the dwarf in the vision?",
        lang="en", category="metaphor",
        answer_chapter="## XLVI. The Vision And The Enigma",
        answer_concept="The dwarf represents the spirit of gravity, weighing Zarathustra down on the mountain path; embodies the small, base, suffering aspect that resists overcoming.",
    ),

    # KO
    NietzscheQuery(
        text="줄타기 광대는 무엇을 상징하는가?",
        lang="ko", category="metaphor",
        answer_chapter="## Prologue",
        answer_concept="줄타기 광대는 인간 자체의 상징. 짐승과 초인 사이에 걸쳐진 줄, 건너가는 행위 그 자체가 중요.",
    ),
    NietzscheQuery(
        text="'몰락'의 의미는 무엇인가?",
        lang="ko", category="metaphor",
        answer_chapter="## Prologue",
        answer_concept="몰락(Untergang)은 차라투스트라가 산에서 내려가는 행위. 극복과 창조를 위한 자발적 희생/이행.",
    ),
    NietzscheQuery(
        text="중력의 영(중력의 정신)이 의미하는 것은?",
        lang="ko", category="metaphor",
        answer_chapter="## LV. 중력의 영",
        answer_concept="중력의 영은 진지함·관습 도덕·자기경멸의 악마. 가벼운 발걸음과 즐거운 창조의 적.",
    ),
    NietzscheQuery(
        text="환영 속 난쟁이의 의미는?",
        lang="ko", category="metaphor",
        answer_chapter="## XLVI. 환영과 수수께끼",
        answer_concept="난쟁이는 중력의 영을 의인화. 산을 오르는 차라투스트라를 짓누름. 극복에 저항하는 비천하고 고통받는 측면.",
    ),
]


assert len(QUERIES) == 24
assert sum(q.lang == "en" for q in QUERIES) == 12
assert sum(q.lang == "ko" for q in QUERIES) == 12
for cat in ["factoid", "concept", "metaphor"]:
    n = sum(q.category == cat for q in QUERIES)
    assert n == 8, f"{cat}: expected 8, got {n}"
