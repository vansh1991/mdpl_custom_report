import frappe

def execute():
    """
    Disable AgentFlo hooks so uninstall of ai_inventory works correctly.
    This patch removes the doc_events hook that tries to access DocType 'Agent'.
    """
    try:
        # Remove agentflo doc_events hook from hooks cache
        if "doc_events" in frappe.local.conf.get("hooks", {}):
            doc_events = frappe.local.conf["hooks"]["doc_events"]
            if "Agent" in doc_events:
                del doc_events["Agent"]
        
        # Also remove from Installed Apps Hooks table (if saved there)
        frappe.db.delete("Installed App Hooks", {"hook": ("like", "%agentflo%")})
        
        frappe.db.commit()
        print("? AgentFlo hooks disabled successfully.")
    except Exception as e:
        print(f"? Error disabling AgentFlo hooks: {e}")
