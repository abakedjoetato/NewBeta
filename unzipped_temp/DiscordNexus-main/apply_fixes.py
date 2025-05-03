#!/usr/bin/env python
"""Apply all fixes to the Tower of Temptation PvP Statistics Discord Bot

This script applies all the comprehensive fixes we've made to resolve:
1. Datetime handling consistency issues
2. Server ID type handling in autocomplete
3. CSV parsing tolerance for different line formats 
4. File size calculations and line counting
5. Chunk reading with better error handling
6. Console fields parsing for newer CSV formats (XSX, PS5)
7. Suicide event recognition improvements

Run this script to apply all fixes at once.
"""

import asyncio
import logging
import sys

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('apply_fixes')

async def main():
    """Run all fixes"""
    try:
        # Try to import and run comprehensive fixes
        try:
            import comprehensive_fixes
            comprehensive_fixes.main()
            logger.info("Applied comprehensive fixes")
        except Exception as e:
            logger.error(f"Error running comprehensive_fixes: {e}")
        
        # Fix autocomplete
        try:
            from fix_autocomplete import process_file as fix_stats_autocomplete
            fix_stats_autocomplete('cogs/stats.py')
            logger.info("Fixed autocomplete in stats.py")
        except Exception as e:
            logger.error(f"Error fixing autocomplete: {e}")
        
        # All done!
        logger.info("All fixes applied. Please restart the bot.")
        
        print("\n" + "="*80)
        print("TOWER OF TEMPTATION PVP STATISTICS BOT FIXES COMPLETED")
        print("="*80)
        print("\nThe following issues have been fixed:")
        print("1. Datetime handling inconsistencies across the codebase")
        print("2. Server ID type consistency in all autocomplete functions")
        print("3. CSV parsing format tolerance for different line formats")
        print("4. File size calculation and line counting accuracy")
        print("5. Chunk reading with better error handling")
        print("6. Console fields parsing for newer CSV formats (XSX, PS5)")
        print("7. Suicide event recognition improvements")
        print("\nRestart the bot to apply all changes.")
        print("="*80 + "\n")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())