#!/usr/bin/env python3
"""
Simple test script for TicketView to diagnose import and instantiation issues
"""
import sys
import os

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_import():
    """Test if we can import the required modules"""
    try:
        print("Testing imports...")
        from ui_components import TicketView
        print("✅ Successfully imported TicketView")
        
        from config import QUICK_REPLIES
        print("✅ Successfully imported QUICK_REPLIES")
        
        return True
    except ImportError as e:
        print(f"❌ Import error: {e}")
        return False
    except Exception as e:
        print(f"❌ Unexpected error during import: {e}")
        return False

def test_ticket_view_creation():
    """Test if we can create a TicketView instance"""
    try:
        print("\nTesting TicketView creation...")
        
        # Mock dependencies
        from unittest.mock import Mock
        mock_intercom = Mock()
        mock_db = Mock()
        
        # Try to create TicketView
        from ui_components import TicketView
        
        # Mock asyncio event loop
        import asyncio
        from unittest.mock import patch
        
        with patch('asyncio.get_running_loop') as mock_loop:
            mock_future = Mock()
            mock_loop.return_value.create_future.return_value = mock_future
            
            view = TicketView(
                ticket_id="12345", 
                conversation_id="conv_123",
                intercom_client=mock_intercom, 
                db_manager=mock_db
            )
            
            print("✅ Successfully created TicketView instance")
            print(f"   - ticket_id: {view.ticket_id}")
            print(f"   - conversation_id: {view.conversation_id}")
            print(f"   - children count: {len(view.children)}")
            
            return True
            
    except Exception as e:
        print(f"❌ Error creating TicketView: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Run the tests"""
    print("=== Simple TicketView Test ===")
    
    # Test imports
    if not test_import():
        print("\n❌ Import test failed. Cannot proceed.")
        return
    
    # Test TicketView creation
    if not test_ticket_view_creation():
        print("\n❌ TicketView creation test failed.")
        return
    
    print("\n✅ All tests passed!")

if __name__ == "__main__":
    main()
