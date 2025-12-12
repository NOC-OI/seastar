


Core to SeaSTAR are three components:

- CLI interpreter
- TUI interpreter
- GUI interpreter

Each allows a different way to interact with a Job

Each job is split into the following components:

- JSON definition of job inputs and outputs, help text, prompts, and preferred CLI options
- Job python script
- Job assets for GUI

Internally jobs should aim to use the provider pattern to process data piece by piece. Files should ideally not be loaded entirely into memory.
