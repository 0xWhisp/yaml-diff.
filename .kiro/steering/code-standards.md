# Code Standards

## Principles

- Write minimal code. Less is better.
- Avoid verbose implementations. If it can be done in fewer lines, do it.
- Don't overengineer. Solve the problem at hand, not hypothetical future problems.
- Prioritize readability and maintainability over cleverness.

## Security

- Use safe parsing methods (e.g., `yaml.safe_load`, not `yaml.load`)
- Validate all external inputs
- Avoid shell injection risks
- Never expose sensitive data in error messages

## Efficiency

- Prefer standard library solutions over external dependencies
- Avoid unnecessary allocations and iterations
- Use appropriate data structures for the task

## Git Commits

- Keep commit messages short and human
- Use present tense, imperative mood
- Examples: "add yaml parser", "fix list diff bug", "update readme"
