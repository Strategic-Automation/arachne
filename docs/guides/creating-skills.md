# Creating Skills: Behavioral Guidelines

Skills in Arachne are not just code; they are "behavioral guidelines" that shape how an agent approaches a specific type of task.

## What is a Skill?

A skill is a directory in `src/arachne/skills/` that contains markdown files or structured text. These files are injected into the agent's prompt to provide domain-specific knowledge and stylistic requirements.

### Key Categories

- **Default Skills**: Standard behaviors for research, summarization, and task execution.
- **Custom Skills**: User-defined skills for specific domains (e.g., coding, project management, customer support).

## How to Add a Skill

1. **Create a Skill Directory**:
   ```bash
   mkdir -p src/arachne/skills/custom/my-new-skill/
   ```

2. **Add Markdown Files**:
   Create a file like `guidelines.md` or `instructions.md`.
   ```markdown
   # My New Skill Guidelines
   
   - Always be concise.
   - Use technical terminology where appropriate.
   - Summarize key findings at the end of every response.
   ```

3. **Initialize the Registry**:
   The `skills.registry` will automatically detect and load your new skill from the `custom/` directory.

4. **Reference in Goals**:
   When you run a goal, the Weaver will automatically identify and inject relevant skills based on the nodes generated.

For MCP server configuration, see [MCP Setup](./mcp-setup.md).