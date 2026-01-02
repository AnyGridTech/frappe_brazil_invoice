import frappe

def get_nfeio_config(is_test_config=0):
    """Helper function to get NFe.io configuration
    
    Returns the production configuration (is_test_config=0) with the highest usage_priority.
    Also includes configs where is_test_config is None/empty for backward compatibility.
    """
    try:
        # Get production NFeIO documents ordered by usage_priority
        # Include None/empty is_test_config for backward compatibility
        nfeio_configs = frappe.get_all(
            "NFeIO",
            fields=["name", "usage_priority", "is_test_config"],
            order_by="usage_priority DESC",
            filters={"is_test_config": is_test_config},
            limit=1
        )

        if len(nfeio_configs) == 0:
            frappe.throw(f"No NFe.io configuration found (with is_test_config={is_test_config}). Please create an NFeIO document with API credentials.")

        nfeio_config = nfeio_configs[0]

        return frappe.get_doc("NFeIO", nfeio_config["name"])
        
    except Exception as e:
        frappe.throw(f"Error when retrieving NFe.io configuration: {str(e)}")
