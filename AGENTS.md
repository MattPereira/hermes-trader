# Instructions

This repo is a hermes agent profile which consists of configurations, skills, plugins, tools and cron jobs

For questions about how hermes agents work, consult the current docs
- https://hermes-agent.nousresearch.com/docs/

## Hermes agent development

- Prefer creating a new skill when the workflow can be expressed as instructions or existing tools.
  - Read the `.agents/skills/hermes-agent-skill-authoring/SKILL.md` before writing a new skill.
- Prefer a tool when it changes Hermes' actual capabilities / interface
  - In order to create a new tool for a hermes agent, you must create a plugin
  - When creating a plugin, read docs first
    - https://hermes-agent.nousresearch.com/docs/guides/build-a-hermes-plugin 

## Validation

- When editing Hermes plugin files, do not declare Python work complete if Basedpyright errors remain

## Git

- Always scan config.yaml for API keys before committing any changes. Do not commit if any api key is present
