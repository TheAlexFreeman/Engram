---

created: '2026-03-20'
last_verified: '2026-03-20'
origin_session: core/memory/activity/2026/03/20/chat-003
source: agent-generated
trust: high
related:
  - normal-form-games-nash-equilibrium.md
  - mechanism-design-revelation-principle.md
  - cheap-talk-crawford-sobel.md
---

# Extensive-Form Games and Backward Induction

## Games in Tree Form

Normal-form games represent simultaneous-move interactions. **Extensive-form games** represent interactions with **temporal structure**: who moves when, what they observe, and what choices they make.

### Components

An extensive-form game specifies:

1. **Players** $N = \{0, 1, \ldots, n\}$ where player 0 is "Nature" (a non-strategic player who moves at random)
2. **Game tree**: a finite directed tree where each node is a **decision node** or a **terminal node**
3. **Assignment of decision nodes to players**: each non-terminal node belongs to exactly one player
4. **Actions**: at each decision node $h$, a set $A(h)$ of available actions
5. **Information sets**: a partition of each player's decision nodes into **information sets** $\mathcal{H}_i$ — nodes in the same information set are indistinguishable to that player
6. **Terminal payoffs**: each terminal node $z$ has a payoff vector $(u_1(z), \ldots, u_n(z))$

A **strategy** for player $i$ in an extensive-form game is a complete contingent plan specifying an action at every information set where $i$ moves — even information sets that will not be reached given earlier choices. This completeness requirement is essential for backward induction.

### Perfect vs. Imperfect Information

A game has **perfect information** if every information set is a singleton — each player knows the full history when they move. Chess, Go, and checkers are perfect-information games. A game has **imperfect information** if some information sets contain multiple nodes — i.e., some player cannot distinguish between decision scenarios.

---

## Backward Induction

**Backward induction** solves a perfect-information game by working backwards from terminal nodes:

1. At terminal nodes, payoffs are given
2. At a decision node $h$ assigned to player $i$, player $i$ chooses the action that maximizes $u_i$ over the subtrees that follow
3. Proceed recursively until the root is reached

The result is a **subgame perfect equilibrium (SPE)** — an equilibrium that specifies rational play at every subgame, including those off the path of equilibrium play.

### Example: Sequential Battle of the Sexes

Player 1 moves first (Opera or Football); Player 2 observes the choice and responds.

```
           Player 1
          /        \
       Opera      Football
        |              |
    Player 2        Player 2
    /     \         /     \
  Opera  Football Opera  Football
  (2,1)   (0,0)  (0,0)  (1,2)
```

Backward induction: Player 2 will choose Opera if P1 plays Opera (payoff 1 > 0) and Football if P1 plays Football (payoff 2 > 0). Player 1 anticipates this: playing Opera → (2,1); playing Football → (1,2). Player 1 prefers Opera → (2,1). Unique SPE: (Opera, "Opera if Opera; Football if Football"). Player 1's first-mover advantage eliminates the coordination problem.

---

## The Centipede Game

**Setup.** Two players alternate moves. At each step, the current player can either "take" (ending the game) or "pass" (extending it). The pot doubles each time a player passes, but the passer gets less than if they took one move later.

A simplified 4-move version with payoffs at terminal nodes:

| Outcome | P1 | P2 |
|---|---|---|
| P1 takes at move 1 | 1 | 0 |
| P2 takes at move 2 | 0 | 2 |
| P1 takes at move 3 | 3 | 1 |
| P2 takes at move 4 | 2 | 4 |
| Both pass to end | 3 | 3 |

**Backward induction prediction:** At move 4, P2 prefers taking (4 > 3). Anticipating this, P1 at move 3 prefers taking (3 > 2, since P2 will take leaving P1 with 2). Anticipating this, P2 at move 2 prefers taking (2 > 1). Anticipating this, P1 at move 1 takes immediately (1 > 0). **SPE: Take immediately.**

**Experimental finding.** Subjects overwhelmingly cooperate for several rounds before taking. The SPE prediction fails dramatically. Why?

- **Limited backward induction depth (bounded rationality)**: players reason only a few steps ahead
- **Altruism and social preferences**: players may value joint payoffs
- **Common knowledge of rationality fails**: if I believe my opponent might not be fully rational (and their rationality is common knowledge), I might cooperate hoping they pass — and this reasoning can unravel the backward induction argument

The centipede game reveals the fragility of backward induction: it requires not just rationality but **common knowledge of rationality** to full depth. Deviation by one "irrational" player can change optimal play for everyone.

---

## Games with Incomplete Information: Bayes-Nash Equilibrium

In many real interactions, players have **private information** — about their own preferences, costs, or types — that others cannot directly observe.

**Bayesian game.** $(N, A, T, p, u)$ where:
- $T_i$ is the **type set** of player $i$ (representing private information)
- $p(t_1, \ldots, t_n)$ is the **prior distribution** over type profiles (commonly assumed common knowledge)
- $u_i(a, t)$ is player $i$'s payoff under action profile $a$ and type profile $t$

A **strategy** in a Bayesian game is a mapping $\sigma_i : T_i \to \Delta(A_i)$ from types to (possibly mixed) actions.

A **Bayes-Nash equilibrium (BNE)** is a strategy profile $\sigma^*$ such that for every player $i$ and every type $t_i$:

$$\sigma_i^*(t_i) \in \arg\max_{a_i \in A_i} \mathbb{E}_{t_{-i}}\left[ u_i(a_i, \sigma_{-i}^*(t_{-i}), t) \mid t_i \right]$$

Each player best-responds to the **expected** behavior of others, averaging over others' types using the conditional prior.

### First-Price Sealed-Bid Auction (BNE example)

Players have private valuations $v_i$ drawn i.i.d. from $[0,1]$. Highest bidder wins and pays their bid. 

In the unique symmetric BNE with $n$ players, each player bids $b_i(v_i) = \frac{n-1}{n} v_i$ — bidding strictly below valuation. The calculation requires each player to optimize expected payoff accounting for their bid's probability of winning against others' equilibrium bidding strategies.

---

## Application to Multi-Agent AI

### Tool-Use Sequences as Extensive-Form Games

When an AI agent chooses a sequence of tools or subtask assignments, the interaction has extensive-form structure:

- **Decision nodes**: each step where the agent (or a subagent) makes a choice
- **Information sets**: what the agent knows at each step (prior outputs, available tools, system state)
- **Backward induction**: reasoning about downstream effects to inform current choices

An agent with bounded rationality (limited forward planning depth) plays as if it cannot perform full backward induction — a realistic model of current LLM planning limitations.

### Anticipating Subagent Defection

In a multi-agent system with a **principal** (orchestrating agent) and **subagents** (executing agents):
- The interaction is an extensive-form game: the principal moves first (assigns tasks), subagents respond
- Subagents have private information about their capabilities, biases, and objectives
- Subagent "defection" (misreporting, shortcutting, or pursuing other objectives) is a strategic response to their incentives

Anticipating subagent behavior requires the principal to reason about the subgame beginning at each subagent's decision point — essentially computing a subgame perfect equilibrium of the multi-agent interaction.

### Information Sets and Observability

Whether agents observe each other's actions is a fundamental design variable:
- **Observation = perfect information** → backward induction applies; agents anticipate downstream reactions
- **No observation = imperfect information** → Bayes-Nash reasoning; agents must infer from available signals
- Transparency mechanisms (logging, auditing) move a game from imperfect to perfect information, changing the equilibrium structure — typically toward better coordination and more accountable behavior

---

## Key Concepts Summary

| Concept | Definition |
|---|---|
| Extensive-form game | Game with temporal structure, decision tree, information sets |
| Strategy | Complete contingent plan for every information set |
| Perfect information | Every information set is a singleton |
| Backward induction | Solve from terminal nodes recursively to root |
| Subgame perfect equilibrium | Nash equilibrium that specifies rational play in *every* subgame |
| Centipede game | SPE prediction (take immediately) fails experimentally — backward induction requires common knowledge of rationality |
| Bayesian game | Incomplete information game; players have private types |
| Bayes-Nash equilibrium | Best-respond to expected behavior of others averaging over their types |

---

## See also

- `normal-form-games-nash-equilibrium.md` — foundations; Nash equilibrium in simultaneous games
- `mechanism-design-revelation-principle.md` — mechanism design uses extensive-form thinking to design revelation games
- `prisoner-dilemma-coordination-games.md` — social dilemmas as normal-form games