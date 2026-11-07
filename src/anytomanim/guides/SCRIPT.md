# SCRIPT — stage 2 spec (host model executes this)

Turn `brief.md` into `beats.json` (schema: `beats-schema.json`). Write an original
explanation: learn how the reference builds understanding, rather than borrowing
its sentences or decorating a list with “But,” “So,” and “Now.”

## What separates 3b1b narration from ours

From 8 3b1b videos against our 18. 

| | 3b1b | Ours |
|---|---|---|
| Adjacent sentences reusing a content term | 47% | 20% |
| Sentences addressing "you" | 38% | 7% |
| Sentences with an explicit question | 5.6% | 8.8% |
| Sentences starting with a connector | 27% | 27% |
| Selected passages that work a case before generalizing | 5 of 5 | 4 of 9 |

The surface is already close: we ask more questions and use as many connectors.
What is missing is underneath. **Each sentence should pick up what the last one
left on the table**, and the viewer should be doing something. Adding "But" and
"So" to a list does not fix it, and neither do more analogies.

These are observations, not quotas. English and Chinese are measured differently,
and Chinese naturally omits subjects.

## Build a whole argument before dividing it into beats

**Opening: establish an observable discrepancy.** Put an object, a task, or a
result in front of the viewer. Establish what they would expect and what needs
explaining. A question can be implicit. The first punctuation-marked questions
start at 40.22s / 48.96s / 336.63s / 53.96s / 396.48s in Gaussian integral /
Moser / CLT / Convolutions / Holograms respectively. These are caption-row starts,
not necessarily the instant the interrogative clause begins. CLT opens with a
board; Holograms with an impossible-looking scene. Neither waits for its first
question mark to become interesting. For a short film, compress this setup;
do not copy a long video's elapsed times or demand an immediate question mark.

**Escalation: let each result create the next need.** Work a case, make a
prediction, expose its limitation, then introduce the tool that addresses that
limitation. A useful planning chain is: observed behavior → provisional rule →
failure or missing explanation → improved mechanism → original question revisited.
The chain is a planning aid, not a required sequence of chapter headings.
Record what is still unexplained after each result. Do not make the viewer wait
through unrelated background to manufacture suspense.

**Middle: reopen the specific gap.** A solved calculation can leave the original
mystery intact. Gaussian integral gets the area, then returns to why circles
belong in a population story. Moser gets a region formula, then asks why the
initial powers of two almost worked. Change the viewer's task: predict a
parameter sweep, inspect one part, or test the provisional explanation. Keep a
recognizable object or quantity through the change. Do not insert a generic
“Now let's explore another important concept.”

**Ending: return to the opening object with new powers.** Replay the original
case or prediction and let the mechanism explain it. State which assumption
made the argument work and what remains open. CLT returns to the actual board's
violations of its simplified assumptions; Holograms returns to information on a
boundary. An explicit next-video promise is legitimate if this film has already
delivered its stated result. Avoid ending with an interchangeable list of terms.

Before splitting the prose, draft a private question ledger: question → evidence
needed → answer location → remaining limitation. Then split at changes of task,
not at every sentence. Do not add ledger fields to `beats.json`.

## Sentence continuity is the main constraint

Write continuous prose first. For each sentence, identify the **given** (an object,
quantity, result, or question already available) and the **new** thing it adds.
Start from the given; end where the next sentence can take hold. Repeat a precise
noun when a pronoun would have two possible antecedents. Keep the viewer's job
concrete: count these pairs, compare these heights, follow this term.

Every adjacent pair needs a describable relationship: consequence, contrast,
restriction, worked instance, generalization, objection, or return. “Also” is
appropriate only when the argument actually needs an additional independent fact.
A connector cannot supply a missing inference. If the paragraphs can be shuffled
without damaging the explanation, rewrite them as a chain of dependencies.

Make the visual chain identical to the verbal chain:

| Spoken relationship | Required visual continuity |
|---|---|
| This value is used next | Box the source and carry a copy into its destination; retain its origin. |
| Only this factor changes | Keep the rest of the expression and its position; move the changed factor. |
| The same quantity in another representation | Preserve its color, anchor, or projection while the new representation grows. |
| A case becomes a general rule | Keep the case's structure while replacing the varying inputs. |
| A parameter causes a different result | Keep axes and baseline fixed; change the parameter and dependent result together. |
| A temporary assumption ends | Restore the earlier state before resuming the main question. |

At a beat boundary, write `visual` as **retain → change → reveal** in ordinary
imperative prose. Name the incoming object and the outgoing state. For example:
“Retain the bowl and yellow point; lengthen only the proposed step; reveal that
its endpoint is higher.” A new page of formulas cannot substantiate “therefore.”

## Ten writing moves to choose from

Use only moves that advance this argument. Our counterexamples are literal narration
from the indicated tools run; beat IDs locate them under `full/<run>/beats.json`.

### 1. Give the viewer something to investigate

**When:** opening or introducing a new mechanism. **Do:** establish one visible
case and an observation the viewer can check before naming the abstraction.


**Our counterexample:** “這正是梯度下降的想法。”
(`gradient__terra__tools`, b01) labels the topic immediately after its question.
The label supplies no reason to choose a step. Keep the point on the slope and
let the next action test a candidate direction before giving the method's name.

### 2. Turn the previous result into the next task

**When:** changing operations or beats. **Do:** reuse the just-established object,
then explain what must now be done to it and why. Change the task, not the subject.


**Our counterexample:** “變成多個變數時，梯度指向局部上升最快的方向；反方向，就是局部下降最快的方向。”
(`gradient__sol__tools`, b04) follows two one-dimensional moves with a vector
assertion. Show how the same directional question now permits sideways movement;
carry the old point into the contour view before introducing the vector.

### 3. Invite a falsifiable prediction

**When:** the viewer has enough information to guess. **Do:** specify what stays
fixed and what will change; let the change occur before stating the result.


**Our counterexample:** “係數揭曉：偶數頻率是零；奇數頻率的振幅是四除以πn，隨頻率倒數縮小。”
(`fourier__luna__tools`, b05) announces coefficients without a prediction or
visible computation supporting those values. Ask what cancellation predicts for
one even harmonic, then show the signed contributions. Withhold the answer only
while the viewer has a useful task; local checks may be answered immediately.

### 4. Use “but” to identify a real shortfall

**When:** a result is correct but insufficient. **Do:** say exactly what it fails
to explain, retain the result, and make that gap motivate the next step.


**Our counterexample:** “但這只描述附近。” (`gradient__sol__tools`, b05) contains
the right qualification but leaves “nearby” untested. Lengthen the same downhill
step until the landing height rises; now the qualification has a visible reason.

### 5. Compute a case, then compress its structure

**When:** introducing notation or a general rule. **Do:** work one manageable
input completely; retain its parts as the input becomes a variable. Explain what
is invariant. One example motivates a claim; it does not prove every case.


**Our counterexample:** “例如，編號是雜湊值除以格子數的餘數。”
(`hashtable__luna__tools`, b03) calls a general recipe an example. Use an actual
key and table size, obtain a bucket, and only then replace those values by symbols.

### 6. Explain what survives a change of representation

**When:** moving between a picture and symbols, or adding a dimension. **Do:**
name the common quantity and preserve its visual identity. Say what the new
representation buys before asking the viewer to learn it.


**Our counterexample:** “這個規律可以寫成一條式子：只用奇數倍頻，每一項的振幅等於頻率倍數的倒數，最後整體乘上四除以圓周率。”
(`fourier__terra__tools`, b05) verbally recites the rule; its visual instruction
only says to expand the series. Keep the colored harmonic beside its same-colored
term; make “this rule” point to the correspondence already established.

### 7. Voice an objection at the moment it becomes justified

**When:** an assumption, limitation, or unexplained maneuver would trouble an
attentive viewer. **Do:** state the objection, test it, and delimit the claim.
Admit an exploratory maneuver when its motivation is not yet available.


**Our counterexample:** “它們不是隨便湊形狀，而是彼此正交的方向，能逐步補上誤差。”
(`fourier__luna__direct`, `fourier_video.py`, `captions[3]`) introduces
orthogonality as reassurance before showing what it means. Ask whether adding
a frequency spoils the earlier measurement; demonstrate its zero contribution.
Do not invoke a technical term as a substitute for the missing explanation.

### 8. Mark a detour and return with its result

**When:** temporarily simplifying, normalizing, or isolating a subproblem.
**Do:** state the temporary change and what will be restored. Return to the same
object, explicitly carrying the sub-result back into the main argument.


**Our counterexample:** “回到這個碗。” (`gradient__sol__tools`, b06) returns by
name, but its visual instruction introduces three bowl plots after an intervening
formula. Keep a small copy of the original bowl and point through that detour;
restore it before adding comparison cases. A return must recover a state, not
merely repeat a noun.

### 9. Narrow attention before explaining a mechanism

**When:** the full arrangement hides a local relationship. **Do:** select one
representative object, suppress interference, and explain its interaction before
restoring the whole. Give an observation task and leave time to complete it.


**Our counterexample:** “要測一種頻率，就將方波乘上正弦波，再對整個週期積分。”
(`fourier__luna__tools`, b04) jumps to a whole-period operation. First select a
single horizontal position, show its two heights and their signed product,
then sweep the position and accumulate the result.

### 10. Use an analogy to transfer a specific operation

**When:** an unfamiliar operation has a familiar structural counterpart.
**Do:** identify the paired parts, use the correspondence once, then return to
the actual object and state where the analogy stops.


**Our counterexample:** “想像你站在山坡上，眼前只有腳下的坡度。”
(`gradient__terra__tools`, b01) is an effective invitation but not yet a mapping.
Make position the input and height the objective value. A gradient step updates
coordinates; it is not a ball rolling under gravity or a promise to reach the
global minimum. Avoid introducing a second metaphor to explain the first.

## Let narration and choreography divide the work

Say the **task, reason, identity, assumption, and interpretation**. Let the image
show **position, trajectory, repeated arithmetic, shape change, and comparison**.
Speak a number when the argument depends on its value; leave incidental ticks
and repeated intermediate values visible. Do not read every term of a long
formula. Introduce the operation and explain the terms that carry the reasoning.
Conversely, a color change cannot silently establish independence, a limit,
orthogonality, or the difference between a local and global claim.

The card numbering is stable within the local fourteen-card study. These are
choices for the `visual` specification, not mandatory effects:

| Cards | Narration's job | Visual's job |
|---|---|---|
| 1 Change only the changing part; 2 Carry a boxed source | Identify the changed factor or source once; explain why the substitution is legal. | Preserve unchanged symbols; carry the source into the result. |
| 3 Enlarge the conclusion; 4 Move the old expression aside | State the interpretation of the result, then reuse it as the next given. | Dim the derivation; keep useful old content available. |
| 5 Count while the quantity grows; 14 Vary one parameter | Ask for a prediction; identify the variable and what stays fixed. | Update the value and result together; keep discrete counts discrete. Card 14 is tentative in the study. |
| 6 Make space with the camera; 7 Color follows meaning | Explain the new relationship; refer to the same quantity by the same name. | Keep the main diagram and persistent color identity as space is added. |
| 8 Keep the old quantity in the new view | State the preserved measurement and the purpose of the new representation. | Align anchors or projections. Tentative evidence; do not force an embedding when none exists. |
| 9 Detour and return | Announce the temporary assumption and explicitly end it. | Save, alter, then restore the relevant state. |
| 10 Example becomes general expression; 11 Fixed comparison baseline | Explain what generalizes, or what single difference is being compared. | Keep the structure or baseline; avoid replacing all comparison cases at once. |
| 12 Product becomes dimensions; 13 One representative before the whole | Name each factor's meaning, or ask the viewer to inspect one unit. | Show the factors on a unit, then accumulate or restore the whole. |

Use “here,” “this slice,” or “notice the gap” only when one visible target is
unambiguous **at that phrase**. Identify it before introducing another competing
object. Keep its referent alive across the beat boundary. Specify the target and
cue in `visual`; “show the formula” is insufficient for a spoken “this factor.”

Stop introducing new claims when the viewer must inspect, count, or compare.
An invitation to look should be followed by the promised action and a brief
space for observation before interpretation. Do not fill that space with a
second definition. Motion can continue meaningfully while speech pauses: keep
the sweep or simulation running with the comparison baseline fixed. For a static
identity check, let the result settle without distracting decoration. Plan the
observation window in `visual`, not as a spoken “[pause]” token. Coordinate its
implementation with SCENE_GUIDE's timing limits; do not invent a new JSON field
or assume punctuation creates a precisely timed TTS silence. Measure the WAV,
then preview the cue and action together. Caption gaps alone do not prove where
the original author intentionally paused.

## Write Chinese as spoken Chinese

Transfer the reasoning, not English syntax. Prefer a known topic followed by
one new action: “這支箭頭先留著。把步子拉長，落點還會更低嗎？” Use “那這一步呢？”
when its referent is visible, rather than translating every “Now” into “現在”.
Useful relationships sound like “剛才只換了方向。那步子多大呢？” / “先別換圖。” /
“可是，這還沒解釋……” / “把剛才那個值放回去。” Do not mechanically alternate them.

Use short clauses around a hard inference, and allow a longer sentence when its
clauses share one subject. Our observed median of 17 Han characters is not a
prescription. Split when the subject or viewing task changes, not at an arbitrary
character count. Read aloud: each clause must attach to the previous one without
requiring the listener to reconstruct a nested English relative clause. Prefer
“沿這個方向，走同樣小的一步，下降最多” over stacking modifiers before “方向”.

Chinese can omit “你” and “我們.” Use “你看這裡” for an actual observation,
“我們先固定步長” for a shared decision, and “我還沒解釋……” for an honest missing
step. Do not add pronouns to match the English percentages. Avoid workbook
transitions such as “首先，介紹定義；其次，介紹性質” unless the ordering is itself
what the viewer needs to understand.

Introduce the ordinary meaning before the technical label: “位置動一點，高度會怎麼變？
描述這個變化率的，就是導數。” Keep terminology consistent, including the chosen
regional vocabulary (梯度、學習率、雜湊/哈希). Distinguish scalar derivative from
vector gradient; one-dimensional sign is not literally an arrow in the graph's
vertical direction. Distinguish choosing the negative-gradient **direction** from
choosing a finite **step** that actually decreases the objective.

Put mathematical notation on screen; give narration an explicit pronunciation.
Say “艾克斯的平方除以二” or “位置的平方除以二,” not “平方的一半” with the variable
missing. Say “圓周率,” “零點五,” and “二分之一” rather than leaving mixed script
for TTS to guess. For O(1), explain “平均工作量不隨資料筆數增加,” then give its
name “平均常數時間”; avoid teaching the notation merely as “歐一”. Keep compact
symbols in `subtitle` if useful. The Chinese and English versions must preserve
the same mathematical qualifications, but need not share sentence boundaries.

## Objective revision checklist

Check the prose before synthesis, and check cue timing again after rendering:

- [ ] The opening names a drawable object/task and an unresolved discrepancy;
      neither is merely a topic title or a question mark.
- [ ] Every adjacent sentence pair has a named relationship and an identifiable
      shared referent or explicitly motivated new subject. Mark these privately;
      a connector alone does not pass.
- [ ] Every beat after the first names its incoming visual state and what changes;
      every cut that discards the shared object has an explicit reason.
- [ ] The question ledger locates an answer or an explicit deferral for every
      substantive question. Each delay contains work needed for that answer.
- [ ] Every new general rule has a worked instance or a stated reason for leading
      with the abstraction. “For example” is followed by an instantiated case.
- [ ] Every “but/so/therefore” identifies the actual contrast, premise, or result.
      Write that dependency down; remove connectors with no dependency.
- [ ] Every deictic phrase identifies exactly one object available at that cue;
      `visual` specifies how to select it, and preview confirms it is visible.
- [ ] Every analogy names its correspondences and a limit; every change of
      representation identifies what quantity stays the same.
- [ ] The ending revisits the opening task, states the delivered result and its
      assumptions, and labels any remaining question or next-video promise.
- [ ] Every symbol needed by speech has a pronunciation; every numerical example
      and limiting claim has been checked. Local claims stay local.
- [ ] Each requested observation has a named action/window with no competing new
      explanation; preview confirms that the viewer can finish it before the next
      claim. No duration is presented as measured until audio exists.
- [ ] With beat IDs and headings removed, every pronoun and given still has an
      identifiable antecedent in prior prose or the specified visible state. Then
      validate IDs and schema, synthesize, measure, and revise visuals to real audio.

## beats.json shape

```json
{
  "title": "Why Sums Look Bell-Shaped",
  "language": "en",
  "beats": [
    {"id": "b01", "narration": "spoken text, 1-3 sentences",
     "visual": "what is on screen during this beat (imperative)",
     "est_seconds": 10}
  ]
}
```

- 8–14 beats typical; content decides length (a `--target-seconds` preference is
  a soft hint only).
- `visual` is a short imperative: "draw a skewed histogram left, stamp a teal
  copy sliding along the axis". It becomes the codegen's spec — be drawable.
- `anytomanim tts --beats beats.json` then fills in, per beat, `audio_file` +
  `audio_seconds` (real measured duration — the animation timing source of
  truth) and bookkeeping (`audio_narration`, `audio_voice`, `audio_fingerprint`).
  Resume checks narration, mode, voice, style, backend and clone sample content;
  only changed beats resynthesize. Legacy manifests still load, but their first
  TTS run resynthesizes once because the old metadata cannot prove those inputs
  match. Don't hand-edit these fields. IDs must match `b[0-9]{2,}` and be unique;
  invalid or duplicate IDs fail before synthesis.
