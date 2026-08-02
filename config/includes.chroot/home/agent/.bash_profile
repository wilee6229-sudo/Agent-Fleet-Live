if [ -z "$TMUX" ] && [ -z "$FLEET_STARTED" ]; then
    export FLEET_STARTED=1
    echo ""
    echo "╔══════════════════════════════════════╗"
    echo "║       AGENT FLEET LIVE               ║"
    echo "╠══════════════════════════════════════╣"
    echo "║  fleet start  — start agents         ║"
    echo "║  fleet stop   — stop agents          ║"
    echo "║  fleet status — check status         ║"
    echo "║  fleet hyprland — desktop mode       ║"
    echo "║  Auto-starting agents in 3s...       ║"
    echo "║  (Ctrl+C to skip, then type 'fleet') ║"
    echo "╚══════════════════════════════════════╝"
    sleep 3
    fleet start
    echo "Type 'tmux attach -t fleet' to see agents"
    echo "Launching Hyprland desktop..."
    fleet hyprland
fi
