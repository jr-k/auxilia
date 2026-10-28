MEMORY_STATE_KEY = "loaded_memory_ids"

LIST_MEMORY_CATEGORIES_TOOL = "list_memory_categories"
GET_MEMORIES_TOOL = "get_memories"
SET_MEMORY_TOOL = "set_memory"
DELETE_MEMORY_TOOL = "delete_memory"
DELETE_MEMORY_CATEGORY_TOOL = "delete_memory_category"

MEMORY_TOOL_NAMES = frozenset(
    {
        DELETE_MEMORY_CATEGORY_TOOL,
        DELETE_MEMORY_TOOL,
        LIST_MEMORY_CATEGORIES_TOOL,
        GET_MEMORIES_TOOL,
        SET_MEMORY_TOOL,
    }
)
