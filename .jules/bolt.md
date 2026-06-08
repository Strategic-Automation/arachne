## 2025-05-24 - Cache repeated API calls for Model Limits during execution
**Learning:** In a graph execution environment where nodes are dynamically instantiated and run, shared setup tasks like detecting model capabilities can lead to a storm of synchronous network requests. `NodeExecutor` resolves limits using `get_model_limits` per-node execution, which queries OpenRouter or Ollama via HTTP to check capabilities. Because these limits don't change within a single session, this causes an unnecessary ~1s delay *per node*.
**Action:** When inspecting execution or compilation loops, always check if invariant external metadata (like API rate limits, model token windows, or capabilities) is being fetched dynamically. Apply in-memory caching like `functools.lru_cache` to short-circuit these redundant synchronous I/O operations and significantly speed up parallel execution and node bootstrapping.

## 2026-06-08 - Return .model_copy() when caching Pydantic models
**Learning:** When using `functools.lru_cache` to cache responses that are mutable objects like Pydantic models (e.g., `ModelLimits`), returning the cached object directly allows downstream code to accidentally mutate the shared instance in the cache.
**Action:** Always append `.model_copy()` to the returned value of the cached inner function to ensure consumers receive a distinct, isolated copy.

## 2026-06-08 - Pass primitive types to lru_cache
**Learning:** When trying to cache a function with `functools.lru_cache` that accepts a Pydantic model like `Settings`, the caching fails with `TypeError: unhashable type` because Pydantic models are mutable and therefore unhashable. Trying to pass dummy classes is a brittle anti-pattern.
**Action:** Create an inner cached function (`_cached_xyz`) that accepts only the specific primitive, scalar properties needed from the unhashable object, and have the outer function extract and pass those properties.
