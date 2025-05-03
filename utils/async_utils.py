"""
Asynchronous utilities for the Tower of Temptation PvP Statistics Discord Bot.

This module provides:
1. Background task management with automatic recovery
2. Asynchronous caching with TTL support
3. Task queue management for rate limiting
4. Retry functionality for unreliable operations
"""
import asyncio
import functools
import inspect
import logging
import time
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable, Awaitable, TypeVar, Generic, Tuple, Set, Union

logger = logging.getLogger(__name__)

# Type variables for function signatures
T = TypeVar('T')
R = TypeVar('R')

class BackgroundTask:
    """Background task management with automatic recovery
    
    This class provides a way to run background tasks with automatic
    recovery in case of exceptions.
    """
    
    _tasks: Set[asyncio.Task] = set()
    _loop: Optional[asyncio.AbstractEventLoop] = None
    
    @classmethod
    def set_event_loop(cls, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for background tasks
        
        Args:
            loop: Event loop to use
        """
        cls._loop = loop
    
    @classmethod
    def get_loop(cls) -> asyncio.AbstractEventLoop:
        """Get the event loop for background tasks
        
        Returns:
            asyncio.AbstractEventLoop: Event loop
        """
        if cls._loop is None:
            try:
                cls._loop = asyncio.get_running_loop()
            except RuntimeError:
                cls._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cls._loop)
        
        return cls._loop
    
    @classmethod
    def create(
        cls,
        coro: Awaitable,
        name: Optional[str] = None,
        restart_on_failure: bool = False,
        max_retries: int = 3,
        retry_delay: float = 5.0
    ) -> asyncio.Task:
        """Create a background task
        
        Args:
            coro: Coroutine to run
            name: Task name (optional)
            restart_on_failure: Whether to restart on failure
            max_retries: Maximum number of retries
            retry_delay: Delay between retries in seconds
            
        Returns:
            asyncio.Task: Created task
        """
        task_name = name or coro.__name__
        
        # Wrapper to handle exceptions and task cleanup
        async def _task_wrapper():
            retries = 0
            while True:
                try:
                    await coro
                    logger.info(f"Background task {task_name} completed successfully")
                    break
                except asyncio.CancelledError:
                    logger.info(f"Background task {task_name} was cancelled")
                    break
                except Exception as e:
                    logger.error(f"Background task {task_name} failed with exception: {e}")
                    logger.error(traceback.format_exc())
                    
                    if not restart_on_failure:
                        break
                    
                    retries += 1
                    if retries > max_retries:
                        logger.error(f"Background task {task_name} exceeded maximum retries ({max_retries})")
                        break
                    
                    logger.info(f"Restarting background task {task_name} in {retry_delay} seconds (retry {retries}/{max_retries})")
                    await asyncio.sleep(retry_delay)
        
        # Create task and add to set
        loop = cls.get_loop()
        task = loop.create_task(_task_wrapper(), name=task_name)
        cls._tasks.add(task)
        
        # Add callback to remove task from set when done
        task.add_done_callback(lambda t: cls._tasks.remove(t) if t in cls._tasks else None)
        
        return task
    
    @classmethod
    def cancel_all(cls) -> None:
        """Cancel all background tasks"""
        for task in cls._tasks:
            task.cancel()
    
    @classmethod
    def get_all(cls) -> List[asyncio.Task]:
        """Get all background tasks
        
        Returns:
            List[asyncio.Task]: List of tasks
        """
        return list(cls._tasks)
    
    @classmethod
    def get_by_name(cls, name: str) -> List[asyncio.Task]:
        """Get tasks by name
        
        Args:
            name: Task name
            
        Returns:
            List[asyncio.Task]: List of tasks
        """
        return [task for task in cls._tasks if task.get_name() == name]

class AsyncCache:
    """Asynchronous caching with TTL support
    
    This class provides a way to cache results of asynchronous functions
    with expiration times.
    """
    
    _cache: Dict[str, Dict[Tuple, Tuple[Any, float]]] = {}
    _cleaning_task: Optional[asyncio.Task] = None
    _cleaning_interval: float = 300.0  # 5 minutes
    
    @classmethod
    def cached(cls, ttl: float = 60.0):
        """Decorator for caching async function results
        
        Args:
            ttl: Time-to-live in seconds
            
        Returns:
            Callable: Decorated function
        """
        def decorator(func):
            # Get function qualname for cache key
            func_key = func.__qualname__
            
            # Initialize cache for this function if needed
            if func_key not in cls._cache:
                cls._cache[func_key] = {}
            
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Create cache key from args and kwargs
                key_args = args
                key_kwargs = tuple(sorted((k, v) for k, v in kwargs.items()))
                cache_key = (key_args, key_kwargs)
                
                # Check if result is in cache and not expired
                if cache_key in cls._cache[func_key]:
                    result, expiry = cls._cache[func_key][cache_key]
                    if time.time() < expiry:
                        return result
                
                # Execute function and cache result
                result = await func(*args, **kwargs)
                cls._cache[func_key][cache_key] = (result, time.time() + ttl)
                
                # Start cleaning task if not already running
                if cls._cleaning_task is None or cls._cleaning_task.done():
                    cls._cleaning_task = BackgroundTask.create(
                        cls._clean_cache(),
                        name="async_cache_cleaner",
                        restart_on_failure=True
                    )
                
                return result
            
            return wrapper
        
        return decorator
    
    @classmethod
    def invalidate(cls, func: Callable, *args, **kwargs) -> None:
        """Invalidate cache entry for a function with specific arguments
        
        Args:
            func: Function
            *args: Function args
            **kwargs: Function kwargs
        """
        # Get function qualname for cache key
        func_key = func.__qualname__
        
        if func_key not in cls._cache:
            return
        
        # Create cache key from args and kwargs
        key_args = args
        key_kwargs = tuple(sorted((k, v) for k, v in kwargs.items()))
        cache_key = (key_args, key_kwargs)
        
        # Remove from cache
        if cache_key in cls._cache[func_key]:
            del cls._cache[func_key][cache_key]
    
    @classmethod
    def invalidate_all(cls, func: Optional[Callable] = None) -> None:
        """Invalidate all cache entries for a function or all functions
        
        Args:
            func: Function (optional - if None, invalidates all cache)
        """
        if func is None:
            # Clear all cache
            cls._cache.clear()
        else:
            # Clear cache for specific function
            func_key = func.__qualname__
            if func_key in cls._cache:
                cls._cache[func_key].clear()
    
    @classmethod
    async def _clean_cache(cls) -> None:
        """Clean expired cache entries"""
        while True:
            current_time = time.time()
            
            # Iterate through all functions in cache
            for func_key in list(cls._cache.keys()):
                func_cache = cls._cache[func_key]
                
                # Remove expired entries
                expired_keys = [
                    key for key, (_, expiry) in func_cache.items()
                    if current_time > expiry
                ]
                
                for key in expired_keys:
                    del func_cache[key]
                
                # Remove empty function caches
                if not func_cache:
                    del cls._cache[func_key]
            
            # Sleep until next cleaning
            await asyncio.sleep(cls._cleaning_interval)

class AsyncRetry:
    """Retry functionality for unreliable operations
    
    This class provides a way to automatically retry async functions
    with configurable backoff strategy.
    """
    
    @staticmethod
    async def retry(
        func: Callable[..., Awaitable[T]],
        *args,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        exceptions: Tuple[Exception, ...] = (Exception,),
        **kwargs
    ) -> T:
        """Retry an async function
        
        Args:
            func: Function to retry
            *args: Function args
            max_retries: Maximum number of retries
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Backoff factor
            exceptions: Exceptions to catch
            **kwargs: Function kwargs
            
        Returns:
            T: Function result
        """
        last_exception = None
        
        for retry_count in range(max_retries + 1):
            try:
                return await func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                
                # If this was the last retry, re-raise the exception
                if retry_count >= max_retries:
                    logger.error(f"Max retries ({max_retries}) reached for {func.__name__}")
                    raise
                
                # Calculate delay with exponential backoff
                delay = min(base_delay * (backoff_factor ** retry_count), max_delay)
                
                logger.warning(
                    f"Retry {retry_count + 1}/{max_retries} for {func.__name__} "
                    f"in {delay:.2f}s after error: {e}"
                )
                
                await asyncio.sleep(delay)
        
        # This should never happen, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Unexpected error in retry logic")
    
    @classmethod
    def retryable(
        cls,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 30.0,
        backoff_factor: float = 2.0,
        exceptions: Tuple[Exception, ...] = (Exception,)
    ):
        """Decorator for retrying async functions
        
        Args:
            max_retries: Maximum number of retries
            base_delay: Base delay in seconds
            max_delay: Maximum delay in seconds
            backoff_factor: Backoff factor
            exceptions: Exceptions to catch
            
        Returns:
            Callable: Decorated function
        """
        def decorator(func):
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                return await cls.retry(
                    func,
                    *args,
                    max_retries=max_retries,
                    base_delay=base_delay,
                    max_delay=max_delay,
                    backoff_factor=backoff_factor,
                    exceptions=exceptions,
                    **kwargs
                )
            return wrapper
        return decorator

class AsyncThrottler:
    """Task queue manager for rate limiting
    
    This class provides a way to limit the rate of async function calls
    to avoid overloading external services.
    """
    
    _buckets: Dict[str, 'AsyncThrottler.Bucket'] = {}
    
    class Bucket:
        """Rate limit bucket"""
        
        def __init__(self, rate_limit: int, time_period: float):
            self.rate_limit = rate_limit
            self.time_period = time_period
            self.tokens = rate_limit
            self.last_refill = time.time()
            self.lock = asyncio.Lock()
        
        async def acquire(self) -> bool:
            """Acquire a token from the bucket
            
            Returns:
                bool: True if token acquired, False otherwise
            """
            async with self.lock:
                # Refill tokens based on time passed
                current_time = time.time()
                time_passed = current_time - self.last_refill
                
                if time_passed > self.time_period:
                    # More than one period has passed, fully refill
                    self.tokens = self.rate_limit
                    self.last_refill = current_time
                elif time_passed > 0:
                    # Partially refill based on time passed
                    tokens_to_add = int((time_passed / self.time_period) * self.rate_limit)
                    if tokens_to_add > 0:
                        self.tokens = min(self.rate_limit, self.tokens + tokens_to_add)
                        self.last_refill = current_time
                
                # Check if we have tokens available
                if self.tokens > 0:
                    self.tokens -= 1
                    return True
                
                return False
        
        async def wait_for_token(self) -> None:
            """Wait until a token is available"""
            while True:
                if await self.acquire():
                    return
                
                # Calculate time until next token
                time_to_next = self.time_period / self.rate_limit
                await asyncio.sleep(time_to_next)
    
    @classmethod
    def get_or_create_bucket(cls, key: str, rate_limit: int, time_period: float) -> 'AsyncThrottler.Bucket':
        """Get or create a rate limit bucket
        
        Args:
            key: Bucket key
            rate_limit: Number of tokens
            time_period: Time period in seconds
            
        Returns:
            Bucket: Rate limit bucket
        """
        if key not in cls._buckets:
            cls._buckets[key] = cls.Bucket(rate_limit, time_period)
        
        return cls._buckets[key]
    
    @classmethod
    def throttled(cls, rate_limit: int, time_period: float, key: Optional[str] = None):
        """Decorator for throttling async functions
        
        Args:
            rate_limit: Number of operations
            time_period: Time period in seconds
            key: Bucket key (optional - defaults to function name)
            
        Returns:
            Callable: Decorated function
        """
        def decorator(func):
            # Get bucket key
            bucket_key = key or func.__name__
            
            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                # Get or create bucket
                bucket = cls.get_or_create_bucket(bucket_key, rate_limit, time_period)
                
                # Wait for token
                await bucket.wait_for_token()
                
                # Execute function
                return await func(*args, **kwargs)
            
            return wrapper
        
        return decorator

def get_background_stats() -> Dict[str, int]:
    """Get statistics about background tasks
    
    Returns:
        Dict: Task statistics
    """
    tasks = BackgroundTask.get_all()
    
    stats = {
        'total': len(tasks),
        'running': sum(1 for t in tasks if not t.done()),
        'completed': sum(1 for t in tasks if t.done() and not t.cancelled()),
        'cancelled': sum(1 for t in tasks if t.cancelled()),
        'failed': sum(1 for t in tasks if t.done() and not t.cancelled() and t.exception() is not None)
    }
    
    return stats