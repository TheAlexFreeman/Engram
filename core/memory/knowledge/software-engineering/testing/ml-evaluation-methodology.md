---
created: 2026-03-20
last_verified: 2026-03-20
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: medium
type: knowledge
related:
  - behavioral-testing-and-red-teaming.md
  - testing-foundations-epistemology.md
  - knowledge/ai/
  - ../ai-engineering/ai-code-review-and-quality.md
---

# ML/AI Evaluation Methodology

Evaluating machine learning and AI systems requires extending classical testing principles with new challenges: the absence of a complete oracle, the statistical nature of model outputs, the risk of data contamination, and the difficulty of distribution shift. This file covers the principled methodology for valid ML evaluation.

---

## 1. Training-test contamination

**The foundational requirement:** The evaluation dataset must not have been seen during training. If training data and test data overlap, evaluation measures memorization — not generalization.

**Why contamination is subtle:**
- Direct overlap is obvious; indirect overlap is not — a model pretrained on a web crawl may have ingested test set examples
- Benchmark contamination for LLMs: popular benchmarks (MMLU, HumanEval, GSM8K) have been incorporated into training corpora by some labs, rendering them invalid for evaluating those models
- Prompt-level contamination: even if examples weren't in the training set, a benchmark's `format` or `few-shot examples` may have been in fine-tuning data
- Near-duplicate contamination: test examples that are paraphrases of training examples

**Detecting contamination:**
- N-gram overlap analysis between training and test sets (perplexity-based detection)
- Canary insertion: add unique, fake facts to training data and test whether the model reproduces them
- Memorization probing: query the model with the beginning of test examples and see if it completes them verbatim
- Differential evaluation: compare model performance on a known-clean held-out set vs. the potentially contaminated benchmark; suspicious gap → possible contamination

**Standard protocol:** Define and freeze the test set before any model training begins. Use time-based splits where appropriate (models trained on data up to T are evaluated on data from T+ε to T+window). Treat the test set as a write-once, consume-once resource.

---

## 2. Cross-validation protocols

Cross-validation enables statistically valid generalization estimates from small datasets by using all data for both training and evaluation.

### 2.1 K-fold cross-validation

1. Partition the dataset into k folds (typically k=5 or k=10)
2. For each fold i: train on all folds except fold i; evaluate on fold i
3. Report the mean and variance of the k evaluation scores

```
Fold 1: [Train | Train | Train | Train | Test]
Fold 2: [Train | Train | Train | Test  | Train]
Fold 3: [Train | Train | Test  | Train | Train]
Fold 4: [Train | Test  | Train | Train | Train]
Fold 5: [Test  | Train | Train | Train | Train]
```

**Why k=5 or k=10:** These are empirically good tradeoffs between bias (k=2 has high bias — small training sets) and variance (k=N = leave-one-out has high variance from near-identical training sets).

### 2.2 Stratified k-fold

For classification with class imbalance, ensure each fold preserves the original class proportion. Avoid fold distributions where some classes are absent or severely underrepresented.

### 2.3 Leave-one-out (LOO-CV)

k = N (each example is its own fold). Lowest bias but highest computational cost and highest variance for small datasets. Use only when N is small (<100) and each model train is computationally cheap.

### 2.4 Nested cross-validation

Required when hyperparameter selection is part of the modeling pipeline:
- **Outer loop:** k-fold CV for unbiased generalization estimate
- **Inner loop:** k-fold CV within the training fold for hyperparameter selection
- Never select hyperparameters using the outer test fold

```
Nested CV structure:
  Outer fold 1: [Inner CV for HP selection] → Test on fold 1
  Outer fold 2: [Inner CV for HP selection] → Test on fold 2
  ...
```

Failure to use nested CV for HPO produces optimistic generalization estimates — the validation set used for HP selection has leaked information into the model selection process.

### 2.5 Time-series cross-validation

Standard k-fold is invalid for time-series data — future data cannot be used to predict past data. Use **walk-forward validation** (expanding or rolling window):

```
Fold 1: [1→T₁ train | T₁→T₂ test]
Fold 2: [1→T₂ train | T₂→T₃ test]
Fold 3: [1→T₃ train | T₃→T₄ test]
```

---

## 3. Evaluation metric choice

The metric must match the actual goal of the model. Mismatched metrics produce deployment failures.

### 3.1 Classification metrics

**Accuracy** = (TP + TN) / (TP + TN + FP + FN). Misleading for imbalanced classes. On a dataset with 95% negative examples, a model that always predicts negative achieves 95% accuracy while being completely useless.

**Precision** = TP / (TP + FP). Of the items classified as positive, what fraction actually are? High precision = few false alarms.

**Recall (sensitivity)** = TP / (TP + FN). Of all actual positives, what fraction did the model find? High recall = few missed positives.

**F1 score** = harmonic mean of precision and recall = 2PR / (P + R). Balances precision and recall equally. Use F1 when missing a positive and falsely labeling a negative are equally bad.

**$F_\beta$ score** = $(1 + \beta^2) \cdot \frac{PR}{\beta^2 P + R}$. β > 1 weights recall higher (cost of missing a positive > cost of a false alarm); β < 1 weights precision higher.

**Area under ROC (AUROC):** Probability that the model ranks a positive instance above a negative. Robust to class imbalance; insensitive to the specific decision threshold.

**Average Precision (AP) / Area under Precision-Recall curve:** Better than AUROC for severely imbalanced datasets (information retrieval, anomaly detection).

### 3.2 Regression metrics

**MAE (Mean Absolute Error):** $\frac{1}{n}\sum |y_i - \hat{y}_i|$. Robust to outliers. Measures average absolute error.

**MSE / RMSE:** $\sqrt{\frac{1}{n}\sum (y_i - \hat{y}_i)^2}$. Penalizes large errors quadratically. Sensitive to outliers; RMSE has same units as input.

**MAPE (Mean Absolute Percentage Error):** $\frac{1}{n}\sum |\frac{y_i - \hat{y}_i}{y_i}|$. Scale-invariant but undefined when $y_i = 0$ and biased (asymmetric).

### 3.3 Generation metrics (NLP)

**BLEU** (Bilingual Evaluation Understudy): n-gram overlap between generated and reference text. Correlates poorly with human judgment; rewards exact phrase repetition; inadequate for open-ended generation.

**ROUGE** (Recall-Oriented Understudy for Gisting Evaluation): n-gram recall between generated summary and reference. Better than BLEU for summarization; still n-gram based.

**BERTScore:** Computes similarity by comparing contextual BERT embeddings. Higher correlation with human judgment than n-gram metrics; still not sufficient for nuanced quality assessment.

**Human evaluation:** For generation quality, human judgment remains the gold standard. Use standardized rating scales (1-5 Likert), inter-rater agreement (Cohen's κ), and sufficiently large sample sizes (≥200 examples for statistical power).

**LLM-as-judge:** Using a stronger LLM to evaluate outputs of a weaker model or to evaluate both models head-to-head. Fast and scalable; introduces model bias (models tend to prefer their own style); use human calibration to validate the LLM evaluator.

### 3.4 Calibration metrics

Calibration measures whether model confidence matches empirical accuracy. A well-calibrated model predicts P(correct) = 0.8 for examples it assigns 80% confidence.

**Brier Score** = $\frac{1}{n}\sum (p_i - y_i)^2$. Combines calibration and accuracy. Perfect calibration + perfect accuracy = 0.

**Expected Calibration Error (ECE):** Bin predictions by confidence; compute weighted average difference between confidence and accuracy in each bin.

**Reliability diagram:** Plot confidence bin (x-axis) vs. accuracy in that bin (y-axis). Perfect calibration = diagonal. Overconfident models are above the diagonal; underconfident below.

---

## 4. Benchmark design principles

**Behavioral coverage:** A valid benchmark should test the full range of the claimed capability, not a convenient proxy. A math benchmark that only tests arithmetic is not a valid benchmark for "mathematical reasoning."

**Difficulty calibration:** A benchmark should span easy, medium, and difficult examples. If all evaluated models consistently achieve near 100%, the benchmark has saturated — it is no longer informative. Human ceiling measurement provides reference.

**Adversarial examples:** Include examples specifically designed to probe failure modes. A sentiment classifier that correctly labels obvious examples but is sensitive to negation should fail on "I don't dislike this product."

**Ceiling and floor effects:** Benchmark design pitfalls:
- **Ceiling:** Too easy — advanced models all cluster near 100%; discrimination is poor
- **Floor:** Too hard — all models cluster near chance; discrimination is poor

**Dataset bias and artifacts:** Many NLP benchmarks contain annotation artifacts — patterns in the dataset that correlate with the label but don't reflect the intended capability. Models trained on these datasets learn the artifact, not the capability. Example: hypothesis text in NLI datasets containing negation words are often labeled "contradiction" regardless of context.

**Dynamic benchmarks:** Fixed benchmarks become contamination risks and saturate over time. Dynamic benchmarks (Dynabench) involve ongoing human adversarial data collection: humans write examples that fool current models; these are added to the benchmark. This maintains difficulty over time.

---

## 5. Dataset shift

**Distribution shift:** A mismatch between the distribution of data used for training/evaluation and the distribution encountered in deployment.

**Types of shift:**

| Type | What changes | Example |
|------|-------------|---------|
| **Covariate shift** | P(X) changes; P(Y|X) unchanged | Spam words shift seasonally |
| **Concept drift** | P(Y|X) changes; P(X) unchanged | User intent behind a query changes |
| **Prior probability shift** | P(Y) changes; P(X|Y) unchanged | Class balance shifts in deployment |
| **Dataset shift (general)** | Joint P(X,Y) changes | Any of the above in combination |

**IID vs. OOD evaluation:**
- **IID (In-distribution) evaluation:** Test set is drawn from the same distribution as training data. Standard CV is IID evaluation.
- **OOD (Out-of-distribution) evaluation:** Test set is drawn from a different distribution. Reveals generalization vs. memorization.

**Why OOD evaluation matters:** A model may achieve 95% accuracy on IID test data but 60% accuracy on OOD data from a different demographic, time period, or domain. The deployment performance depends on whether deployment matches the training distribution, which it often does not.

**Evaluating under shift:**
- Deliberately create OOD test splits (different time periods, different user demographics, different geographic regions)
- Measure performance under known shifts and report all of them, not just the best
- Use domain-generalization benchmarks that explicitly include distribution shift in their design

---

## 6. Goodhart's Law in ML evaluation

**As stated:** "When a measure becomes a target, it ceases to be a good measure."

**In ML:** When benchmark performance becomes a target for optimization, models overfit to the benchmark. This takes several forms:

1. **Dataset-specific overfitting:** Training on examples of the same form as the benchmark (e.g., training on MMLU-style questions to improve MMLU score without improving general reasoning)
2. **Training distribution overlap:** Pretraining data includes exact or near-duplicate benchmark examples
3. **Metric optimization without goal optimization:** RLHF that optimizes human preference scores without actually becoming more helpful; BLEU optimization without improving translation quality
4. **Leaderboard overfitting:** Repeated evaluation on the same test set leads to selection bias — models are implicitly selected for test-set performance across many submissions

**Defenses:**
- Hold out a private test set (never publish examples; evaluate on it only for final releases)
- Use multiple diverse benchmarks to reduce the surface area for overfitting to any single one
- Report results on live user evaluation, not just fixed benchmarks
- Treat published benchmark scores with appropriate skepticism; require diverse evidence

---

## 7. Evaluation reporting standards

**All results should include:**
- Dataset details: size, class distribution, collection method, known biases
- Metric choice and rationale
- Confidence intervals or standard errors (benchmarks are samples; results have variance)
- Comparison to baselines (random, majority class, prior art)
- Evaluation code and test split (for reproducibility)
- Known limitations of the evaluation

**Statistical significance:** Report whether differences between models are statistically significant. A 1% accuracy difference on a 100-example test set is not meaningful. Use bootstrap confidence intervals, paired t-tests, or McNemar's test for classification comparisons across the same test set.

**Disaggregated evaluation:** Report metrics broken down by demographic group, input type, domain, and any known subpopulation where performance might differ. Aggregate metrics can hide systematic disparities — a model with 90% average accuracy may have 70% accuracy for one subgroup.
