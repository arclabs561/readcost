# The effect of word position on eye-movements in sentence and paragraph reading

Victor Kuperman, Michael Dambacher, Antje Nuthmann, Reinhold Kliegl. 2010.
Quarterly Journal of Experimental Psychology 63(9), 1838-1857. DOI
[10.1080/17470211003602412](https://doi.org/10.1080/17470211003602412);
read from the University of Potsdam postprint (Postprints der Universität
Potsdam, Humanwissenschaftliche Reihe 235).

Read: full (postprint of the published article, all sections, tables 1 to
3; figures described from captions and text). Title and authors match.

## Claim

Fixation times rise over the first few words of a line and over the last
several words of a single-line sentence (a "start-up" and a "wrap-up"
effect), independent of length, frequency, predictability and lexical
status. In paragraph reading (Dundee) the effect follows visual lines,
not sentences: position in a sentence has no effect, and wrap-up appears
only on the last line of a screen.

## Method and data

- Single-line sentences: Potsdam Sentence Corpus (German, 144 sentences,
  222 readers), DEMONIC and DMORPH (Dutch, 55 and 28 readers); first-pass
  single fixation and gaze duration, first and last words excluded.
- Paragraphs: Dundee English, sentences of 5 to 15 words, line-edge
  words excluded (25,350 points).
- z-string control (letters replaced by z, 46 readers).
- Mixed models with cubic polynomials of absolute or relative position
  and controls for words n-1, n, n+1.

## Results (numbers that matter)

- Single-line sentences: penultimate words 30 to 45 ms longer than second
  words; 10 to 20 ms rise at the start, 20 to 40 ms at the end of long
  sentences.
- Dundee: position in sentence not significant (p > .1); position in line
  matters only on the screen's fifth line (about 40 ms from second to
  penultimate word); other lines speed up toward the end.
- z-strings show no position effect; start-up tracks increasing incoming
  saccade amplitude.
- Dependency distance (Alpino parses, Dutch) was not a significant
  predictor.

## What the full text qualifies

The authors expand "wrap-up" to several final words. Their paragraph
conclusions rest on one corpus.

## For readcost (used / tested / candidate)

Not cited. Bearing on the reading-time model (src/readcost/readtime.py),
whose features include word index and relative position in the paragraph
(following Cekini et al.):

- Position effects in eye tracking are tied to the visual layout (line,
  screen), not to text structure. OneStop showed one paragraph per screen;
  readcost applies the learned position effect to Markdown documents whose
  line breaks depend on the viewer. The position features may therefore
  encode OneStop's display rather than anything about the text. Worth an
  ablation: drop the two position features and compare OneStop and Provo
  error.
- Wrap-up as a multi-word ramp rather than a single final-word cost; see
  also the Meister 2022 note.

## Open questions

- How much of readcost's tree importance goes to position, and does
  removing it change Provo error (Provo shows short paragraphs on one
  screen)?
