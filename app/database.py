"""
Database Configuration and Utilities for PostgreSQL and SQLite
Provides connection management and common database operations
Supports both PostgreSQL (production) and SQLite (cost-optimized)
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
    def use_sqlite():
        """Check if SQLite should be used instead of PostgreSQL"""
        return os.environ.get('USE_SQLITE', 'false').lower() in ('true', '1', 'yes')
    
    @staticmethod
    def get_sqlite_uri():
        """Get SQLite database URI"""
        # SQLite database will be stored in instance folder
        db_path = os.environ.get('SQLITE_DB_PATH', 'instance/rssbsne.db')
        
        # Ensure the directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir and not os.path.exists(db_dir):
            os.makedirs(db_dir, exist_ok=True)
        
        # Return absolute path for SQLite
        if not os.path.isabs(db_path):
            base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
            db_path = os.path.join(base_dir, db_path)
        
        return f"sqlite:///{db_path}"
    
    @staticmethod
    def get_postgres_uri():
        """Get PostgreSQL database URI"""
        db_host = os.environ.get('DB_HOST', 'localhost')
        db_port = os.environ.get('DB_PORT', '5432')
        db_name = os.environ.get('DB_NAME', 'rssbsne')
        db_user = os.environ.get('DB_USER', 'postgres')
        db_password = os.environ.get('DB_PASSWORD', '')
        
        if not db_password and os.environ.get('FLASK_ENV') != 'development':
            logger.warning("DB_PASSWORD not set in production environment!")
        
        # PostgreSQL connection URI format
        # postgresql://username:password@host:port/database
        return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    
    @staticmethod
    def get_database_uri():
        """
        Constructs database connection URI based on USE_SQLITE environment variable.
        
        SQLite Mode (USE_SQLITE=true):
        - Uses local SQLite database file
        - No external database server required
        - Perfect for low-traffic applications
        - Environment variable: SQLITE_DB_PATH (default: instance/rssbsne.db)
        
        PostgreSQL Mode (USE_SQLITE=false or not set):
        - Connects to PostgreSQL database (RDS or local)
        - Required environment variables:
          - DB_HOST: PostgreSQL host
          - DB_PORT: PostgreSQL port (default: 5432)
          - DB_NAME: Database name
          - DB_USER: Database username
          - DB_PASSWORD: Database password
        """
        if DatabaseConfig.use_sqlite():
            logger.info("Using SQLite database")
            return DatabaseConfig.get_sqlite_uri()
        else:
            logger.info("Using PostgreSQL database")
            return DatabaseConfig.get_postgres_uri()
    
    @staticmethod
    def get_sqlalchemy_config():
        """Returns SQLAlchemy configuration dictionary"""
        base_config = {
            'SQLALCHEMY_DATABASE_URI': DatabaseConfig.get_database_uri(),
            'SQLALCHEMY_TRACK_MODIFICATIONS': False,  # Disable FSAModifications overhead
            'SQLALCHEMY_ECHO': os.environ.get('FLASK_ENV') == 'development',  # Log SQL in dev
        }
        
        # Add connection pool settings only for PostgreSQL
        if not DatabaseConfig.use_sqlite():
            base_config.update({
                'SQLALCHEMY_POOL_SIZE': int(os.environ.get('DB_POOL_SIZE', '10')),
                'SQLALCHEMY_POOL_TIMEOUT': int(os.environ.get('DB_POOL_TIMEOUT', '30')),
                'SQLALCHEMY_POOL_RECYCLE': int(os.environ.get('DB_POOL_RECYCLE', '3600')),
                'SQLALCHEMY_MAX_OVERFLOW': int(os.environ.get('DB_MAX_OVERFLOW', '20')),
            })
        
        return base_config


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
