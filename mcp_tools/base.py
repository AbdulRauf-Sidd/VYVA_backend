from pydantic import BaseModel, ConfigDict


class MCPBaseModel(BaseModel):
    """Base Pydantic model for all MCP tool inputs (and nested schemas).

    Configures ``extra="ignore"`` so that protocol-specific keys the MCP
    runtime may inject (e.g. ``id``, ``name``, ``_meta``) are silently
    dropped instead of raising ``unexpected_keyword_argument`` validation
    errors.
    """

    model_config = ConfigDict(extra="ignore")
