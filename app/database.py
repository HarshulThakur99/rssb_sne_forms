"""
Database Configuration and Utilities for PostgreSQL
Provides connection management and common database operations
"""
import os
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.orm import scoped_session, sessionmaker
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager

logger = logging.getLogger(__name__)

class DatabaseConfig:
    """Database configuration from environment variables"""
    
    @staticmethod
    def get_database_uri():
        """
        Constructs PostgreSQL connection URI from environment variables.
        
        Required environment variables:
        - DB_HOST: PostgreSQL host (e.g., your-rds-instance.region.rds.amazonaws.com)
        - DB_PORT: PostgreSQL port (default: 5432)
        - DB_NAME: Database name (e.g., rssbsne)
        - DB_USER: Database username
        - DB_PASSWORD: Database password
        
        For local development, you can use:
        - DB_HOST=localhost
        - DB_PORT=5432
        - DB_NAME=rssbsne_dev
        - DB_USER=postgres
        - DB_PASSWORD=your_password
        """
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'rssbsne')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_password = os.environ.get('DB_PASSWORD', '')
        
        if not db_password and os.environ.get('FLASK_ENV') != 'development':
            logger.warning("DB_PASSWORD not set in production environment!")
        
        # PostgreSQL connection URI format
        # postgresql://username:password@host:port/database
        uri = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
        
        return uri
    
    @staticmethod
    def get_sqlalchemy_config():
        """Returns SQLAlchemy configuration dictionary"""
        return {
            'SQLALCHEMY_DATABASE_URI': DatabaseConfig.get_database_uri(),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,  # Disable FSAModifications overhead
            'SQLALCHEMY_ECHO': os.environ.get('FLASK_ENV') == 'development',  # Log SQL in dev
            'SQLALCHEMY_POOL_SIZE': int(os.environ.get('DB_POOL_SIZE', '10')),
            'SQLALCHEMY_POOL_TIMEOUT': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
            'SQLALCHEMY_POOL_RECYCLE': int(os.environ.get('DB_POOL_RECYCLE', '3600')),
            'SQLALCHEMY_MAX_OVERFLOW': int(os.environ.get('DB_MAX_OVERFLOW', '20')),
        }


def init_db(app):
    """
    Initialize database with Flask app
    
    Args:
        app: Flask application instance
    
    Usage:
        from app.models import db
        from app.database import init_db
        
        init_db(app)
    """
    from app.models import db
    
    # Apply configuration
    app.config.update(DatabaseConfig.get_sqlalchemy_config())
    
    # Initialize SQLAlchemy with app
    db.init_app(app)
    
    logger.info("Database initialized successfully")


def create_tables(app):
    """
    Create all database tables
    
    Args:
        app: Flask application instance
        
    Usage:
        with app.app_context():
            create_tables(app)
    """
    from app.models import db
    
    db.create_all()
    logger.info("All database tables created successfully")


def drop_tables(app):
    """
    Drop all database tables (use with caution!)
    
    Args:
        app: Flask application instance
    """
    from app.models import db
    
    db.drop_all()
    logger.warning("All database tables dropped")


def check_connection():
    """
    Check if database connection is working
    
    Returns:
        bool: True if connection successful, False otherwise
    """
    from app.models import db
    
    try:
        # Execute a simple query
        result = db.session.execute(text('SELECT 1'))
        result.fetchone()
        logger.info("Database connection check: SUCCESS")
        return True
    except Exception as e:
        logger.error(f"Database connection check FAILED: {e}", exc_info=True)
        return False


@contextmanager
def get_db_session():
    """
    Context manager for database sessions with automatic commit/rollback
    
    Usage:
        with get_db_session() as session:
            user = User.query.filter_by(id=1).first()
            session.commit()
    """
    from app.models import db
    
    try:
        yield db.session
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Database session error: {e}", exc_info=True)
        raise
    finally:
        db.session.close()


# Common database query utilities

def get_or_create(session, model, defaults=None, **kwargs):
    """
    Get an existing record or create a new one
    
    Args:
        session: SQLAlchemy session
        model: SQLAlchemy model class
        defaults: Dict of default values for creation
        **kwargs: Filter criteria
        
    Returns:
        tuple: (instance, created) where created is True if new record
    """
    instance = session.query(model).filter_by(**kwargs).first()
    if instance:
        return instance, False
    else:
        params = {**kwargs, **(defaults or {})}
        instance = model(**params)
        session.add(instance)
        return instance, True


def safe_commit(session):
    """
    Safely commit with error handling
    
    Args:
        session: SQLAlchemy session
        
    Returns:
        bool: True if commit successful, False otherwise
    """
    try:
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Commit failed: {e}", exc_info=True)
        return False
