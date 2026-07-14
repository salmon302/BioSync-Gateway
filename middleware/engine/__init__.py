"""
Algorithmic Engines Module
Initializes all mathematical engines for BioSync-Gateway
"""

import logging

logger = logging.getLogger(__name__)


def init_engines():
    """
    Initialize all algorithmic engines.
    Called during application startup.
    """
    logger.info("Initializing algorithmic engines...")
    
    # Import engines to verify they're available
    try:
        from engine import barcode, dilution, signal, pulse
        logger.info("Barcode engine loaded")
        logger.info("Dilution solver loaded")
        logger.info("Signal processing engine loaded")
        logger.info("Pulse engine loaded (mock mode)")
    except ImportError as e:
        logger.warning(f"Some engines not yet implemented: {e}")
    
    logger.info("Algorithmic engines initialization complete")
