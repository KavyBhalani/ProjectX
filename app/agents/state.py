from typing import TypedDict, List, Dict, Any, Optional

class CompanionState(TypedDict):
    user_id: str
    companion_id: str
    gender: str
    input: str
    history: List[Dict[str, str]]
    
    # Context injected during processing
    profile_context: str
    episodic_context: str
    
    # Safety
    is_safe: bool
    safety_reason: Optional[str]
    
    # Generated response
    response: str
    
    # Internal flag for extraction
    trigger_extraction: bool
