#!/usr/bin/env python3
"""
Helios Progress Monitoring Cron Job

This script runs periodically to:
1. Check the health of the Helios implementation
2. Verify GitHub repo status
3. Monitor CI/CD pipeline
4. Report progress and blockages
5. Auto-restart stalled work if needed
"""

import os
import sys
import json
import subprocess
import requests
from datetime import datetime, timedelta
from pathlib import Path

PROJECT_DIR = Path("/home/hermes/helios")
LOG_FILE = PROJECT_DIR / ".progress-monitor.log"
STATE_FILE = PROJECT_DIR / ".progress-state.json"
GITHUB_REPO = "nnc59bpp2m-create/helios"

class ProgressMonitor:
    def __init__(self):
        self.state = self.load_state()
        self.log("Progress monitor started")
    
    def log(self, message: str):
        timestamp = datetime.now().isoformat()
        log_entry = f"[{timestamp}] {message}"
        with open(LOG_FILE, "a") as f:
            f.write(log_entry + "\n")
        print(log_entry)
    
    def load_state(self) -> dict:
        if STATE_FILE.exists():
            try:
                with open(STATE_FILE) as f:
                    return json.load(f)
            except:
                pass
        return {
            "last_check": None,
            "last_commit": None,
            "ci_status": "unknown",
            "health_score": 100,
            "blocked_since": None,
            "restart_count": 0
        }
    
    def save_state(self):
        with open(STATE_FILE, "w") as f:
            json.dump(self.state, f, indent=2)
    
    def run_command(self, cmd: list, cwd: Path = PROJECT_DIR) -> tuple:
        """Run command and return (success, output)"""
        try:
            result = subprocess.run(cmd, cwd=cwd or PROJECT_DIR, capture_output=True, text=True, timeout=60)
            return result.returncode == 0, result.stdout.strip()
        except subprocess.TimeoutExpired:
            return False, "Command timed out"
        except Exception as e:
            return False, str(e)
    
    def check_git_status(self) -> dict:
        """Check git repository status"""
        success, output = self.run_command(["git", "status", "--porcelain"])
        if not success:
            return {"error": output}
        
        has_changes = len(output.strip()) > 0
        
        # Get last commit
        success, last_commit = self.run_command(["git", "log", "-1", "--pretty=format:%H|%s|%ci"])
        
        # Get branch
        success, branch = self.run_command(["git", "branch", "--show-current"])
        
        # Check if pushed to remote
        success, remote_status = self.run_command(["git", "status", "-uno"])
        
        return {
            "clean": not has_changes,
            "changes": output.strip().split("\n") if has_changes else [],
            "branch": branch,
            "last_commit": last_commit,
            "remote_status": remote_status
        }
    
    def check_docker_services(self) -> dict:
        """Check if Docker services are running"""
        success, output = self.run_command(["docker-compose", "ps", "--format", "json"])
        if not success:
            return {"error": output, "running": False}
        
        services = {}
        for line in output.strip().split("\n"):
            if line:
                try:
                    svc = json.loads(line)
                    services[svc.get("Service", "")] = svc.get("State", "")
                except:
                    pass
        
        expected = ["backend", "frontend", "redis", "ollama"]
        running = all(s in services and services[s] == "running" for s in expected)
        
        return {"services": services, "running": running, "expected": expected}
    
    def check_github_ci(self) -> dict:
        """Check GitHub Actions CI status"""
        try:
            url = f"https://api.github.com/repos/{GITHUB_REPO}/actions/runs?per_page=5"
            headers = {"Accept": "application/vnd.github+json"}
            # Note: Would need GITHUB_TOKEN for authenticated requests
            resp = requests.get(url, headers=headers, timeout=10)
            
            if resp.status_code == 200:
                runs = resp.json().get("workflow_runs", [])
                latest = runs[0] if runs else None
                
                return {
                    "status": latest.get("conclusion") if latest else "unknown",
                    "workflow": latest.get("name") if latest else None,
                    "created": latest.get("created_at") if latest else None,
                    "url": latest.get("html_url") if latest else None
                }
            else:
                return {"status": "error", "code": resp.status_code}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    
    def check_backend_health(self) -> dict:
        """Check backend API health"""
        try:
            resp = requests.get("http://localhost:8000/health", timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                return {"healthy": data.get("status") == "healthy", "data": data}
            return {"healthy": False, "status_code": resp.status_code}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def check_frontend_health(self) -> dict:
        """Check frontend dev server"""
        try:
            resp = requests.get("http://localhost:5173", timeout=5)
            return {"healthy": resp.status_code == 200, "status_code": resp.status_code}
        except Exception as e:
            return {"healthy": False, "error": str(e)}
    
    def calculate_health_score(self, checks: dict) -> int:
        """Calculate overall health score (0-100)"""
        score = 100
        
        # Git clean
        if not checks.get("git", {}).get("clean", True):
            score -= 10
        
        # Docker services
        if not checks.get("docker", {}).get("running", False):
            score -= 30
        
        # Backend health
        if not checks.get("backend", {}).get("healthy", False):
            score -= 25
        
        # Frontend health
        if not checks.get("frontend", {}).get("healthy", False):
            score -= 20
        
        # CI status
        ci_status = checks.get("ci", {}).get("status", "unknown")
        if ci_status == "failure":
            score -= 15
        elif ci_status in ["cancelled", "timed_out"]:
            score -= 10
        
        return max(0, score)
    
    def detect_stalled(self, checks: dict) -> bool:
        """Detect if work has stalled"""
        # Health score below 50
        if checks.get("health_score", 100) < 50:
            return True
        
        # CI failing for more than 1 hour
        ci = checks.get("ci", {})
        if ci.get("status") == "failure":
            created = ci.get("created")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    if datetime.now(created_dt.tzinfo) - created_dt > timedelta(hours=1):
                        return True
                except:
                    pass
        
        # No commits in 24 hours but work in progress
        git = checks.get("git", {})
        if not git.get("clean", True):
            last_commit = git.get("last_commit", "")
            if "|" in last_commit:
                commit_date = last_commit.split("|")[2]
                try:
                    commit_dt = datetime.fromisoformat(commit_date.replace("Z", "+00:00"))
                    if datetime.now(commit_dt.tzinfo) - commit_dt > timedelta(hours=24):
                        return True
                except:
                    pass
        
        return False
    
    def auto_restart(self, checks: dict):
        """Attempt to auto-restart stalled work"""
        self.log("Attempting auto-restart...")
        self.state["restart_count"] += 1
        
        # Restart Docker services if unhealthy
        if not checks.get("docker", {}).get("running", False):
            self.log("Restarting Docker services...")
            self.run_command(["docker-compose", "restart"])
        
        # Re-push git changes if needed
        git = checks.get("git", {})
        if not git.get("clean", True):
            self.log("Uncommitted changes detected, attempting to commit and push...")
            self.run_command(["git", "add", "-A"])
            self.run_command(["git", "commit", "-m", "chore: auto-commit progress"])
            self.run_command(["git", "push"])
        
        # Trigger CI re-run if failed
        ci = checks.get("ci", {})
        if ci.get("status") == "failure":
            self.log("CI failed, triggering re-run...")
            # Would need gh CLI or GitHub API with token
    
    def run_checks(self) -> dict:
        """Run all health checks"""
        self.log("Running health checks...")
        
        checks = {
            "timestamp": datetime.now().isoformat(),
            "git": self.check_git_status(),
            "docker": self.check_docker_services(),
            "ci": self.check_github_ci(),
            "backend": self.check_backend_health(),
            "frontend": self.check_frontend_health()
        }
        
        checks["health_score"] = self.calculate_health_score(checks)
        checks["stalled"] = self.detect_stalled(checks)
        
        # Update state
        self.state["last_check"] = checks["timestamp"]
        self.state["health_score"] = checks["health_score"]
        self.state["ci_status"] = checks["ci"].get("status", "unknown")
        git = checks.get("git", {})
        if git.get("last_commit"):
            self.state["last_commit"] = git["last_commit"]
        
        if checks["stalled"]:
            if self.state["blocked_since"] is None:
                self.state["blocked_since"] = checks["timestamp"]
            self.log(f"WORK STALLED DETECTED! Health score: {checks['health_score']}")
            
            # Auto-restart if not already attempted recently
            if self.state["restart_count"] < 3:
                self.auto_restart(checks)
        else:
            self.state["blocked_since"] = None
        
        self.save_state()
        
        # Log summary
        self.log(f"Health check complete: score={checks['health_score']}, stalled={checks['stalled']}")
        
        return checks

def main():
    monitor = ProgressMonitor()
    checks = monitor.run_checks()
    
    # Exit with error code if stalled
    if checks.get("stalled"):
        sys.exit(1)
    sys.exit(0)

if __name__ == "__main__":
    main()