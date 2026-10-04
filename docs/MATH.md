# Mathematical foundations

Each check in ouroboros-guard rests on one of the results below. Notation: $Y$ the outcome, $X$ the
information legitimately available at prediction time, $\hat Y$ the prediction, $H$ a hypothesis, $E$ an
observation such as "the check passed".

## 1. The information graph

Let $G = (V, E)$ be the directed graph whose nodes are pieces of information (inputs, documents, tool
results, derived artefacts, predictions, outcomes) and whose edges $u \to v$ mean "$u$ was used to produce
$v$". Write $\mathrm{Anc}(v)$ for the set of nodes with a directed path to $v$, and $\tau(v)$ for the time at
which $v$ existed.

**Honest prediction.**

$$Y \notin \mathrm{Anc}(\hat Y) \quad\text{and}\quad \tau(a) < \tau(\hat Y)\ \ \text{for all } a \in \mathrm{Anc}(\hat Y).$$

**Circular argument.** An argument for $C$ is circular when $C \in \mathrm{Anc}(C)$, i.e. $G$ has a cycle
through $C$. Sound reasoning is a directed acyclic graph rooted in independently accepted nodes.

Dates are intervals: a date $d$ of granularity "year" or "month" denotes $[d_0, d_1)$. For a cut-off
instant $c$: $d$ is *before* $c$ iff $d_1 \le c$; *not before* iff $d_0 \ge c$; otherwise *ambiguous*.

## 2. Leakage as conditional mutual information

If the prediction is computed from the legitimate inputs and independent randomness,
$\hat Y = f(X, U)$ with $U \perp (X, Y)$, then

$$I(\hat Y; Y \mid X) \le I(X, U; Y \mid X) = I(U; Y \mid X) = 0 .$$

So $I(\hat Y; Y \mid X) > 0$ certifies a side channel: information about $Y$ reached $\hat Y$ other than
through $X$. This is the formal definition of leakage used here.

**Data processing inequality.** If $Y \to X \to \hat Y$ is a Markov chain, then
$I(Y; \hat Y) \le I(Y; X)$. No processing of $X$, however clever, adds information about $Y$.

## 3. Evidence must be able to fail

Bayes' rule in odds form:

$$\frac{P(H \mid E)}{P(\neg H \mid E)} = K \cdot \frac{P(H)}{P(\neg H)}, \qquad K = \frac{P(E \mid H)}{P(E \mid \neg H)}, \qquad W = \log_2 K \ \text{bits}.$$

$W$ is I. J. Good's weight of evidence. A **circular check** passes whatever the truth:
$P(E \mid H) = P(E \mid \neg H) = 1$, hence $K = 1$, $W = 0$ and the posterior equals the prior.

Example: prior $0.2$; a check with $P(E\mid H)=0.9$, $P(E\mid\neg H)=0.1$ gives $K=9$, $W=3.17$ bits, posterior $0.69$.

**Affirming the consequent.** From $H \Rightarrow C$ and $C$ one may not conclude $H$. In evidence terms,
observing $C$ is weak whenever $P(C \mid \neg H)$ is close to 1, which is the case for any consequence that
was likely to be true anyway. A step $H \Rightarrow C$ can be run backwards only if it is an equivalence
(squaring, multiplying by zero and taking absolute values are not).

## 4. Proofs

Let $A$ be a set of axioms and $\mathrm{Mod}(A)$ its models (possible worlds).

- A valid proof of $T$ from $A$ establishes $\mathrm{Mod}(A) \subseteq \mathrm{Mod}(T)$: it rules out every
  world in which the axioms hold and $T$ fails.
- A circular proof uses $A \cup \{T\}$ and establishes $\mathrm{Mod}(A \cup \{T\}) \subseteq \mathrm{Mod}(T)$,
  which holds for every $T$. It rules out nothing.
- **Soundness:** if $\mathrm{Mod}(A \cup \{\neg T\}) \ne \varnothing$ then $A \nvdash T$. When a statement is
  independent of the axioms (Euclid's parallel postulate relative to absolute geometry), every purported
  proof is either wrong or assumes an equivalent of $T$, which is what check P2 looks for.

## 5. Replicate ceilings

**Binary outcomes.** Each run reports the true outcome $T$ correctly with probability $q \ge \tfrac12$,
independently. Two runs agree with probability

$$a = q^2 + (1-q)^2 \quad\Longrightarrow\quad q = \frac{1 + \sqrt{2a - 1}}{2}.$$

For any predictor $\hat Y$ whose errors are independent of the run's noise,
$P(\hat Y = Y_1) = q\,P(\hat Y = T) + (1-q)\,P(\hat Y \ne T) \le q$, with equality when $\hat Y = T$.
So $q$ is the best accuracy any honest model can reach against a single run. Example: $a = 0.82$ gives $q = 0.90$.

**Continuous outcomes.** With $Y_i = T + e_i$, independent errors of equal variance, the reliability
$R = \mathrm{Var}(T) / \mathrm{Var}(Y) = \mathrm{corr}(Y_1, Y_2)$. For any $f(X)$ with $e_1 \perp (X, T)$, by Cauchy–Schwarz,

$$\mathrm{corr}(f(X), Y_1) = \frac{\mathrm{cov}(f, T)}{\sigma_f\,\sigma_Y} \le \frac{\sigma_T}{\sigma_Y} = \sqrt{R}.$$

## 6. Searching manufactures signal

With $n$ samples, null correlations are approximately $N(0, 1/n)$. The largest of $k$ of them grows like

$$\max_{j \le k} |r_j| \approx \sqrt{\frac{2 \ln k}{n}}$$

(an overestimate for small $n$). With $n = 30$ and $k = 10^4$, simulation gives about $0.67$ from pure noise.
Selecting on the same data used to test (double dipping) reports that maximum as if it were an effect.

## 7. Counting evidence twice

Using data $D$ in both the prior and the likelihood gives $p(\theta \mid D, D) \propto p(D \mid \theta)^2 p(\theta)$.
For Gaussian data the standard error shrinks from $\sigma/\sqrt n$ to $\sigma/\sqrt{2n}$, and a nominal 95%
interval covers the truth with probability $P(|Z| < 1.96/\sqrt 2) \approx 0.834$.

## 8. Adaptive reuse of a test set

If an analyst looks at a test set $m$ times and each look returns one of $s$ possible answers, the transcript
of looks has entropy at most $m \log_2 s$ bits, so at most that much information about the test labels can
enter the analyst's subsequent choices. A keep-or-discard decision leaks up to one bit per look; a few hundred
iterations can leak as many bits as a few hundred binary labels contain. Thresholdout (Dwork et al., 2015)
limits the leak by answering with the training score unless the two differ by more than a noisy threshold.

## 9. Permutation tests

Under the null hypothesis that labels are exchangeable with respect to the inputs, the real score and $B$
scores on permuted labels are exchangeable, so

$$p = \frac{1 + \#\{b : s_b \ge s_{\text{real}}\}}{B + 1}$$

is a valid p-value. The *negative-control* use is different: if the mean of $s_b$ exceeds chance, the
pipeline extracts signal from label noise, which only a leak can do. The permutation must include every
data-dependent step, or the control tests the wrong pipeline.

## 10. Commit-reveal

$c = \mathrm{SHA256}(\mathrm{canonical}(\hat y) \,\|\, s)$ with a uniformly random 256-bit salt $s$.
*Hiding*: without $s$, $c$ gives no practical information about $\hat y$ (the salt defeats guessing a small
prediction space). *Binding*: finding $\hat y' \ne \hat y$ and $s'$ with the same $c$ requires a SHA-256
collision. Publishing $c$ with a trusted timestamp proves the prediction existed at that time.

## 11. Split novelty

For a test item $x$, novelty is $1 - \max_{t \in \text{train}} \mathrm{sim}(x, t)$, with Jaccard similarity of
character $n$-gram sets for strings, cosine for real vectors and Tanimoto ($|a \wedge b| / |a \vee b|$) for bit
vectors. Reporting the score by novelty band separates interpolation from generalisation.

## References

- Ambroise & McLachlan (2002). Selection bias in gene extraction on the basis of microarray gene-expression data. *PNAS* 99, 6562–6566.
- Cover & Thomas (2006). *Elements of Information Theory*, 2nd ed.
- Dwork, Feldman, Hardt, Pitassi, Reingold & Roth (2015). The reusable holdout. *Science* 349, 636–638.
- Golchin & Surdeanu (2024). Time travel in LLMs: tracing data contamination in large language models. *ICLR*.
- Good (1950). *Probability and the Weighing of Evidence*.
- Kapoor & Narayanan (2023). Leakage and the reproducibility crisis in machine-learning-based science. *Patterns* 4, 100804.
- Kaufman, Rosset, Perlich & Stitelman (2012). Leakage in data mining. *ACM TKDD* 6(4), 15.
- Kriegeskorte, Simmons, Bellgowan & Baker (2009). Circular analysis in systems neuroscience. *Nature Neuroscience* 12, 535–540.
- Panickssery, Bowman & Feng (2024). LLM evaluators recognize and favor their own generations. *NeurIPS*.
- Wallach & Heifets (2018). Most ligand-based classification benchmarks reward memorization rather than generalization. *J. Chem. Inf. Model.* 58, 916–932.
