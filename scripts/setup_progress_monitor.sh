#!/bin/bash
# Helios Progress Monitor Setup Script
# Run as: sudo ./setup_progress_monitor.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Setting up Helios Progress Monitor..."

# Install Python dependencies
pip3 install requests pyyaml docker 2>/dev/null || echo "Some pip packages may already be installed"

# Make progress monitor executable
chmod +x "$PROJECT_DIR/scripts/progress_monitor.py"

# Create log files
touch "$PROJECT_DIR/.progress-monitor.log"
touch "$PROJECT_DIR/.progress-cron.log"
touch "$PROJECT_DIR/.docker-watchdog.log"
touch "$PROJECT_DIR/.git-auto-push.log"

# Install systemd service and timer
echo "Installing systemd service..."
sudo cp "$PROJECT_DIR/helios-progress-monitor.service" /etc/systemd/system/
sudo cp "$PROJECT_DIR/helios-progress-monitor.timer" /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable and start timer
sudo systemctl enable helios-progress-monitor.timer
sudo systemctl start helios-progress-monitor.timer

# Also add cron jobs as backup
echo "Setting up cron jobs..."
(crontab -l 2>/dev/null; cat "$PROJECT_DIR/crontab-helios") | crontab -

echo "Setup complete!"
echo ""
echo "Progress monitor will run every 15 minutes via systemd timer."
echo "Cron jobs also configured as backup."
echo ""
echo "Check status:"
echo "  systemctl status helios-progress-monitor.timer"
echo "  journalctl -u helios-progress-monitor -f"
echo ""
echo "Manual run:"
echo "  python3 $PROJECT_DIR/scripts/progress_monitor.py"
echo ""
echo "View logs:"
echo "  tail -f $PROJECT_DIR/.progress-monitor.log"
echo "  tail -f $PROJECT_DIR/.progress-cron.log"