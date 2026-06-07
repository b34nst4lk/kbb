# Daily Log — 2026-06-06 20:51

**Question** (work_experience): What are some key lessons you've learned about designing for maintainability in large-scale systems, and how have you applied those principles to your work as a Tech Lead?

**Rationale**: Jack has extensive experience as a Tech Lead, which likely involved designing complex systems. Asking him about his approach to maintainability will reveal specific knowledge he's gained through hands-on experience.

## Response

For context, the kind of systems that I've worked on are not unusually large in the way FAANG companies are large.

Maintanability is the ease in which a system can be modified, updated, extended or repaired over time.
The topic itself can be split into 2 parts, the technical architecture and implementation, and the knowledge and business context surrounding it.

On the tech itself, I estimate that 9 out of 10 use cases are almost never going to be so large scale that one would require the kind of technical complexity seen in FAANG companies.
Given this, I would say to always start small, and build to the requirements, not for possible requirements.
If you can keep things isolated and independent, do that -> if things are not modified in place by multiple actors, it becomes easier to track what's happening to it
If you can deploy everything in a single artifact, do that -> if you keep deployment simple until you can't, you only have to deal with a large codebase. If you overcomplicate your architecture, you now have a large codebase and a complex architecture to fight against
Most problems are solved problems, research deeply into what others have done before coming up with a novel approach
Show preferences for solutions that require less cognitive overload -> It's easier to tackle a problem if the tools for tackling the problem is simple

There can be more, but these are top of mind


On the knowledge and business context, the human factor cannot be ignored
Engineers who have a good grasp of the business would be better equiped to map that onto functionality in the code. This translates to maintability in that you are less likely to be caught by surprises and edge cases when you see them in code. If fact, you would be puzzled if those are not present where you expect them
Define domains and concepts as simply and clearly as possible to minimize cognitive load. Develop common vocabulary quickly to represent complex ideas


===

How have I applied them to my work as a Tech Lead? I'm no longer a tech lead, but here's what I advocate for

Code base:
1. Always ensure that you write you code in a testable way, and write the tests around it.
2. When in doubt, choose the more braindead approach.
3. In legacy codebases, adopt the scout's rule: leave the place a little better than when you first entered
    a. If you fixed a bug, do what you can to write the test case representing the bug. You now have a new safety net preventing this bug from recurring
    b. If you see a small opportunity to move something out of a function that is doing too much, break it out and see if you can write tests around itself
    c. When learning a new code base, write tests around functions to see what works and what breaks

Technical design
1. First, respect what has come before. It may not be best practice, but a recognizable pattern makes it easier to expect what comes next. Breaking a pattern can cause more confusion.


I would expand further, but the short answer that I seem to be arriving to is to consider the cognitive load an engineer will encounter when they have to touch what you are building.

## Recorded Knowledge

**Designing for Maintainability in Large-Scale Systems**
=====================================================

Maintainability is the ease with which a system can be modified, updated, extended or repaired over time.

### Technical Architecture and Implementation

1. **Start Small**: Build to requirements, not possible requirements.
2. **Isolate Components**: Separate components to track changes easily.
3. **Simple Deployment**: Deploy everything in a single artifact to simplify updates.
4. **Solve Solved Problems**: Research existing solutions before creating novel approaches.
5. **Low Cognitive Overload**: Favor solutions that require less cognitive effort.

### Knowledge and Business Context

1. **Human Factor**: Engineers familiar with the business better map functionality onto code, leading to maintainability.
2. **Clear Vocabulary**: Define domains and concepts simply to minimize cognitive load.
3. **Common Vocabulary**: Develop a shared vocabulary quickly to represent complex ideas.

### Applying Principles as a Tech Lead

* **Code Base**:
	1. Write testable code with accompanying tests.
	2. Prefer a simple, braindead approach when in doubt.
	3. Adopt the "scout's rule" in legacy codebases: leave it better than you found it.
	4. Add safety nets for fixed bugs and write tests around new code.
* **Technical Design**:
	1. Respect existing design patterns to ease future development.

**Inspirational Quote**: Consider the cognitive load an engineer will encounter when interacting with what you're building.
