# Instructions

This repo contains a custom hermes agent profile which consists of configurations, skills, plugins, tools and cron jobs

For questions about how hermes agents work, consult the current docs: https://hermes-agent.nousresearch.com/docs/

## Hermes agent development

- Prefer a skill when the workflow can be expressed as instructions, shell commands, or existing tools.
  - Read the `.agents/skills/hermes-agent-skill-authoring/SKILL.md` before writing a new skill.
- In order to create a new tool for a hermes agent, you must create a plugin
  - When creating a plugin, read the docs first: https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin 

## Validation

- When editing Hermes plugin files, do not declare Python work complete if Basedpyright errors remain
