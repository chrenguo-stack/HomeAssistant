# Stage 2D-8 Isolated Broker Templates V56

These files are inert templates. They contain no address, password, certificate,
key, runnable command, container definition, or production include.

A later private staging step must render all placeholders from an exact execution
manifest. The rendered files remain outside the repository. The temporary
Broker must run outside M401A, T1 and Home Assistant hosts, expose only the exact
`gh-test/<run>/#` ACL, disable persistence and bridging, and be destroyed after
cleanup evidence is complete.
