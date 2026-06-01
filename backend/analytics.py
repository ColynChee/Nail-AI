import json
import os
from datetime import datetime
from typing import Dict, List, Optional
from collections import defaultdict

class AnalyticsManager:
    def __init__(self, log_file: str = "analytics_log.json"):
        self.log_file = log_file
        self.logs = self._load_logs()
    
    def _load_logs(self) -> List[Dict]:
        if os.path.exists(self.log_file):
            try:
                with open(self.log_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return []
        return []
    
    def _save_logs(self):
        with open(self.log_file, 'w', encoding='utf-8') as f:
            json.dump(self.logs, f, ensure_ascii=False, indent=2)
    
    def log_try_on(self, design_id: str, design_name: str, skin_tone: Optional[str] = None, success: bool = True):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "try_on",
            "design_id": design_id,
            "design_name": design_name,
            "skin_tone": skin_tone,
            "success": success
        }
        self.logs.append(log_entry)
        self._save_logs()
    
    def log_analyze_hand(self, skin_tone: str, undertone: str):
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": "analyze_hand",
            "skin_tone": skin_tone,
            "undertone": undertone
        }
        self.logs.append(log_entry)
        self._save_logs()
    
    def get_stats(self) -> Dict:
        try_on_logs = [log for log in self.logs if log['type'] == 'try_on']
        analyze_logs = [log for log in self.logs if log['type'] == 'analyze_hand']
        
        design_counts = defaultdict(int)
        skin_tone_counts = defaultdict(int)
        
        for log in try_on_logs:
            design_counts[log['design_id']] += 1
        
        for log in analyze_logs:
            skin_tone_counts[log['skin_tone']] += 1
        
        sorted_designs = sorted(design_counts.items(), key=lambda x: x[1], reverse=True)
        
        return {
            "total_try_ons": len(try_on_logs),
            "total_analyzes": len(analyze_logs),
            "successful_try_ons": sum(1 for log in try_on_logs if log.get('success', True)),
            "top_designs": [{"design_id": d[0], "count": d[1]} for d in sorted_designs[:5]],
            "skin_tone_distribution": dict(skin_tone_counts),
            "today_try_ons": sum(1 for log in try_on_logs if log['timestamp'].startswith(datetime.now().strftime('%Y-%m-%d'))),
            "updated_at": datetime.now().isoformat()
        }
    
    def get_design_stats(self, design_id: str) -> Dict:
        logs = [log for log in self.logs if log['type'] == 'try_on' and log['design_id'] == design_id]
        return {
            "design_id": design_id,
            "total_try_ons": len(logs),
            "success_rate": sum(1 for log in logs if log.get('success', True)) / max(len(logs), 1)
        }
    
    def clear_logs(self):
        self.logs = []
        self._save_logs()
    
    def get_logs(self, limit: int = 100) -> List[Dict]:
        return self.logs[-limit:]

analytics = AnalyticsManager()

def log_try_on(design_id: str, design_name: str, skin_tone: Optional[str] = None, success: bool = True):
    analytics.log_try_on(design_id, design_name, skin_tone, success)

def log_analyze_hand(skin_tone: str, undertone: str):
    analytics.log_analyze_hand(skin_tone, undertone)

def get_analytics() -> Dict:
    return analytics.get_stats()

def get_design_analytics(design_id: str) -> Dict:
    return analytics.get_design_stats(design_id)