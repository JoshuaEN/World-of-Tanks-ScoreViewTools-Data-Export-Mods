# ScoreViewTools Mod
Mod used with (closed source) ScoreViewTools.

Basically exports various game data to res_mods/ScoreViewTools, specifically Training Room lobby updates and general vehicle data (once per client session).

The exporting of general vehicle data is triggered on loading a training room, rather than at some more logical point (e.g. startup) because there are resources the game needs to load before the export code can run. Running on training room load was a simple work around to this race condition.

## Code Quality
This code is the very definition of prototype turned production, was originally written in 2017 with minor modifications/hotfixes applied to fix breakages due to changes to the client code.

## Building
I used PjOrion v1.3.5.501. Other tools/versions would probably also work.