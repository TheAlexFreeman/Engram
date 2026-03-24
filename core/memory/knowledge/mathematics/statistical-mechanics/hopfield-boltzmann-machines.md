---
created: '2026-03-21'
origin_session: core/memory/activity/2026/03/21/chat-001
source: agent-generated
trust: medium
---

# Hopfield Networks and Boltzmann Machines

## Core Idea

**Hopfield networks** (1982) showed that associative memory — storing and recalling patterns — can be understood as energy minimisation in a system of binary neurons with symmetric connections, directly importing the mathematical framework of the Ising model into computation. **Boltzmann machines** (Hinton & Sejnowski, 1983) added stochastic dynamics and hidden units, creating a generative model that learns a probability distribution over data via the Boltzmann distribution $p \propto e^{-E}$. **Restricted Boltzmann machines** (RBMs) — with bipartite connectivity that enables efficient training — played a pivotal role in the deep learning revival of the 2000s and remain the clearest bridge between statistical physics and neural network theory.

---

## Hopfield Networks

### Architecture

$N$ binary neurons $\sigma_i \in \{+1, -1\}$ with symmetric connections $J_{ij} = J_{ji}$ (no self-connections: $J_{ii} = 0$). The energy function is:

$$E(\boldsymbol{\sigma}) = -\frac{1}{2} \sum_{i \neq j} J_{ij} \sigma_i \sigma_j - \sum_i h_i \sigma_i$$

This is exactly the Ising Hamiltonian with general (not just nearest-neighbour) couplings (see [ising-model-phase-transitions.md](ising-model-phase-transitions.md)).

### Hebb's Rule and Pattern Storage

To store $p$ binary patterns $\boldsymbol{\xi}^1, \dots, \boldsymbol{\xi}^p$, set the weights via **Hebb's rule**:

$$J_{ij} = \frac{1}{N} \sum_{\mu=1}^p \xi_i^\mu \xi_j^\mu$$

This is a rank-$p$ approximation: the weight matrix is the outer-product sum of the stored patterns.

### Retrieval as Energy Minimisation

Starting from an initial state (partial or noisy version of a stored pattern), update neurons asynchronously:

$$\sigma_i \leftarrow \text{sign}\left(\sum_j J_{ij} \sigma_j + h_i\right)$$

Each update decreases or preserves $E$ (guaranteed by the symmetric weight condition). The network relaxes to a local minimum of the energy landscape, which ideally corresponds to a stored pattern.

The stored patterns are **fixed points** (attractors) of the dynamics — the network performs content-addressable memory retrieval by gradient descent on an energy landscape (see [dynamical-systems-fundamentals.md](../dynamical-systems/dynamical-systems-fundamentals.md)).

### Capacity Limits

The network can reliably store approximately $p_{\max} \approx 0.138 N$ patterns (the **Gardner bound**, see [statistical-mechanics-of-learning.md](statistical-mechanics-of-learning.md)). Beyond this threshold:

- **Spurious attractors** appear: linear combinations of stored patterns that are local minima but don't correspond to any stored memory
- **Catastrophic forgetting**: previously stored patterns become unstable
- The transition from reliable retrieval to failure is a **phase transition** in the statistical mechanics sense

### Modern Hopfield Networks

Ramsauer et al. (2021) showed that the **attention mechanism** in transformers can be understood as a continuous-valued Hopfield network with exponential energy:

$$E = -\log \sum_\mu \exp(\boldsymbol{\xi}^\mu \cdot \boldsymbol{\sigma})$$

This "modern Hopfield network" has exponential storage capacity ($\sim e^{N/2}$) and retrieval dynamics equivalent to a single attention layer. The tokens in the context are the stored patterns; the query is the probe state; the attention output is the retrieved memory.

---

## Boltzmann Machines

### From Deterministic to Stochastic Dynamics

Replace deterministic updates with **stochastic** updates governed by the Boltzmann distribution:

$$p(\sigma_i = 1 | \boldsymbol{\sigma}_{\setminus i}) = \frac{1}{1 + \exp(-2\beta \sum_j J_{ij} \sigma_j)}$$

At temperature $T = 1/\beta$, the network samples from $p(\boldsymbol{\sigma}) = \frac{1}{Z} e^{-\beta E(\boldsymbol{\sigma})}$. This converts the Hopfield network from an optimiser to a **sampler** — from finding a single attractor to exploring the full energy landscape probabilistically.

### Visible and Hidden Units

A Boltzmann machine partitions neurons into:

- **Visible units** $\mathbf{v}$: represent observed data
- **Hidden units** $\mathbf{h}$: capture latent structure

The marginal distribution over visible units:

$$p(\mathbf{v}) = \sum_\mathbf{h} \frac{1}{Z} e^{-E(\mathbf{v}, \mathbf{h})}$$

The hidden units allow the model to capture complex distributions over $\mathbf{v}$ that cannot be represented by pairwise interactions among visible units alone. This is the statistical mechanics version of latent variable modelling.

### Learning: The Boltzmann Machine Learning Rule

The gradient of the log-likelihood with respect to weights:

$$\frac{\partial \log p(\mathbf{v})}{\partial J_{ij}} = \langle \sigma_i \sigma_j \rangle_{\text{clamped}} - \langle \sigma_i \sigma_j \rangle_{\text{free}}$$

- **Clamped phase** (positive phase): visible units fixed to data, sample hidden units
- **Free phase** (negative phase): sample both visible and hidden units from the model distribution

This "wake-sleep" structure — contrasting data statistics with model statistics — is the prototype of all contrastive learning methods. The negative phase requires sampling from the model, which involves running MCMC to equilibrium (see [markov-chains-mixing-times.md](../probability/markov-chains-mixing-times.md)) — computationally expensive for general Boltzmann machines.

---

## Restricted Boltzmann Machines (RBMs)

### Bipartite Structure

An RBM restricts connectivity: no visible-visible or hidden-hidden connections. The energy becomes:

$$E(\mathbf{v}, \mathbf{h}) = -\mathbf{v}^\top W \mathbf{h} - \mathbf{b}^\top \mathbf{v} - \mathbf{c}^\top \mathbf{h}$$

The bipartite structure makes the conditional distributions tractable:

$$p(\mathbf{h} | \mathbf{v}) = \prod_j \text{Bernoulli}(\sigma(W^\top_j \mathbf{v} + c_j))$$
$$p(\mathbf{v} | \mathbf{h}) = \prod_i \text{Bernoulli}(\sigma(W_i \mathbf{h} + b_i))$$

where $\sigma$ is the sigmoid function. Each conditional is a product of independent Bernoullis — block Gibbs sampling alternates between layers in a single step.

### Contrastive Divergence (CD)

Hinton (2002) introduced **contrastive divergence** (CD-$k$): instead of running MCMC to equilibrium for the negative phase, run only $k$ steps (typically $k = 1$):

1. Start visible units at data $\mathbf{v}_0$
2. Sample $\mathbf{h}_0 \sim p(\mathbf{h} | \mathbf{v}_0)$
3. Sample $\mathbf{v}_1 \sim p(\mathbf{v} | \mathbf{h}_0)$
4. Gradient $\approx \langle \mathbf{v}_0 \mathbf{h}_0^\top \rangle - \langle \mathbf{v}_1 \mathbf{h}_1^\top \rangle$

CD is biased but works well in practice. Persistent contrastive divergence (PCD) maintains Markov chains across parameter updates for better mixing.

### RBMs in Deep Learning History

RBMs were central to the deep learning revival:

- **Deep belief networks** (Hinton et al., 2006): Stack RBMs, train greedily layer-by-layer, then fine-tune with backpropagation. This showed that deep networks *could* be trained effectively and reignited interest in deep learning.
- **Feature learning**: Each RBM layer learns increasingly abstract features, analogous to successive coarse-graining in renormalisation group theory.
- **Historical significance**: While RBMs have been largely superseded by direct end-to-end trained architectures (CNNs, transformers), they provided the theoretical and practical bridge from statistical physics to modern deep learning.

---

## Energy Landscapes and Attractor Dynamics

### The Loss-Landscape View

The energy function $E(\boldsymbol{\sigma})$ defines a landscape over the space of configurations. Key features:

- **Local minima**: Stored patterns in Hopfield networks; modes of the learned distribution in Boltzmann machines
- **Saddle points**: Transition states between basins of attraction
- **Basin structure**: The set of initial states that converge to a given minimum; defines the "memory" associated with each attractor

This landscape metaphor extends to deep learning loss surfaces, where SGD navigates a high-dimensional energy landscape. The analogy is made precise through the spin glass framework (see [spin-glasses-replica-method.md](spin-glasses-replica-method.md)).

### Simulated Annealing

Kirkpatrick et al. (1983) applied the Boltzmann machine's stochastic dynamics to combinatorial optimisation: start at high $T$ (explore broadly), slowly cool to $T \to 0$ (converge to the global minimum). The cooling schedule determines whether the system gets trapped in local minima or finds the global optimum — a direct application of the mixing time theory (see markov-chains-mixing-times.md).

---

## Connections

- **Partition function**: The normalisation constant $Z$ in Boltzmann machines is the partition function; learning requires estimating its gradient — see [partition-function-free-energy.md](partition-function-free-energy.md)
- **Transformers**: Modern Hopfield networks show that attention is energy-based associative memory with exponential capacity
