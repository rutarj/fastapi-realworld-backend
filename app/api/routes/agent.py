from typing import Any, Dict, List, Optional
import json

from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel
from slugify import slugify

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import tool

from app.api.dependencies.authentication import get_current_user_authorizer
from app.api.dependencies.database import get_repository
from app.db.repositories.articles import ArticlesRepository
from app.db.repositories.comments import CommentsRepository
from app.db.repositories.profiles import ProfilesRepository
from app.models.domain.users import User


router = APIRouter(tags=["agent"])


class AgentRequest(BaseModel):
    query: str


class AgentToolCallResult(BaseModel):
    tool: str
    args: Dict[str, Any]
    result: Any


class AgentResponse(BaseModel):
    response: Any
    tool_calls: Optional[List[AgentToolCallResult]] = None


MAX_QUERY_LENGTH = 2000
MAX_TOOL_CALL_ROUNDS = 3
MAX_LIST_LIMIT = 50


def _build_tools(
    user: Optional[User],
    articles_repo: ArticlesRepository,
    profiles_repo: ProfilesRepository,
    comments_repo: CommentsRepository,
):
    @tool
    async def create_article(
        title: str,
        description: str,
        body: str,
        tags: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create a new article for the current authenticated user."""
        if user is None:
            raise ValueError("Authentication required to create articles.")

        slug = slugify(title)
        logger.info("Agent creating article with slug={}", slug)
        article = await articles_repo.create_article(
            slug=slug,
            title=title,
            description=description,
            body=body,
            author=user,
            tags=tags or [],
        )

        return {
            "article": {
                "slug": article.slug,
                "title": article.title,
                "description": article.description,
                "authorUsername": article.author.username,
            },
        }

    @tool
    async def list_articles(
        tag: Optional[str] = None,
        author: Optional[str] = None,
        limit: int = 20,
        offset: int = 0,
    ) -> Dict[str, Any]:
        """List articles, optionally filtered by tag or author."""
        logger.info(
            "Agent listing articles tag={} author={} limit={} offset={}",
            tag,
            author,
            limit,
            offset,
        )
        safe_limit = min(max(limit, 1), MAX_LIST_LIMIT)
        articles = await articles_repo.filter_articles(
            tag=tag,
            author=author,
            favorited=None,
            limit=safe_limit,
            offset=offset,
            requested_user=user,
        )

        return {
            "articles": [
                {
                    "slug": article.slug,
                    "title": article.title,
                    "description": article.description,
                    "authorUsername": article.author.username,
                }
                for article in articles
            ],
            "articlesCount": len(articles),
        }

    @tool
    async def get_article(slug: str) -> Dict[str, Any]:
        """Get a single article by slug."""
        logger.info("Agent retrieving article slug={}", slug)
        article = await articles_repo.get_article_by_slug(
            slug=slug,
            requested_user=user,
        )
        return {
            "article": {
                "slug": article.slug,
                "title": article.title,
                "description": article.description,
                "body": article.body,
                "authorUsername": article.author.username,
            },
        }

    @tool
    async def get_profile(username: str) -> Dict[str, Any]:
        """Get a user profile by username."""
        logger.info("Agent retrieving profile username={}", username)
        profile = await profiles_repo.get_profile_by_username(
            username=username,
            requested_user=user,
        )

        return {
            "profile": {
                "username": profile.username,
                "bio": profile.bio,
                "image": profile.image,
                "following": profile.following,
            },
        }

    @tool
    async def add_comment(slug: str, body: str) -> Dict[str, Any]:
        """Add a comment to an article identified by slug."""
        if user is None:
            raise ValueError("Authentication required to add comments.")

        logger.info("Agent adding comment for article slug={}", slug)
        article = await articles_repo.get_article_by_slug(
            slug=slug,
            requested_user=user,
        )
        comment = await comments_repo.create_comment_for_article(
            body=body,
            article=article,
            user=user,
        )

        return {
            "comment": {
                "id": comment.id_,
                "body": comment.body,
                "articleSlug": article.slug,
                "authorUsername": comment.author.username,
            },
        }

    @tool
    async def list_comments(slug: str) -> Dict[str, Any]:
        """List comments for an article by slug."""
        logger.info("Agent listing comments for article slug={}", slug)
        article = await articles_repo.get_article_by_slug(
            slug=slug,
            requested_user=user,
        )
        comments = await comments_repo.get_comments_for_article(
            article=article,
            user=user,
        )

        return {
            "comments": [
                {
                    "id": comment.id_,
                    "body": comment.body,
                    "articleSlug": article.slug,
                    "authorUsername": comment.author.username,
                }
                for comment in comments
            ],
        }

    return [
        create_article,
        list_articles,
        get_article,
        get_profile,
        add_comment,
        list_comments,
    ]


@router.post(
    "",
    response_model=AgentResponse,
    name="agent:handle-query",
)
async def handle_agent_query(
    payload: AgentRequest,
    user: Optional[User] = Depends(get_current_user_authorizer(required=False)),
    articles_repo: ArticlesRepository = Depends(get_repository(ArticlesRepository)),
    profiles_repo: ProfilesRepository = Depends(get_repository(ProfilesRepository)),
    comments_repo: CommentsRepository = Depends(get_repository(CommentsRepository)),
) -> AgentResponse:
    """Accept natural language query and call existing CRUD operations via LangChain tools."""
    logger.info("Received agent query")

    try:
        if len(payload.query) > MAX_QUERY_LENGTH:
            raise HTTPException(
                status_code=400,
                detail="Query is too long.",
            )

        tools = _build_tools(user, articles_repo, profiles_repo, comments_repo)
        tools_by_name = {tool.name: tool for tool in tools}

        llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
        llm_with_tools = llm.bind_tools(tools)

        system_message = SystemMessage(
            content=(
                "You are an AI agent for the RealWorld API. "
                "Use the provided tools to read or modify articles, profiles and comments. "
                "When tools are no longer needed, answer the user in natural language."
            ),
        )
        messages: List[Any] = [
            system_message,
            HumanMessage(content=payload.query),
        ]

        tool_call_trace: List[AgentToolCallResult] = []

        for _ in range(MAX_TOOL_CALL_ROUNDS):
            ai_message = await llm_with_tools.ainvoke(messages)
            logger.debug("Agent model output: {}", ai_message)

            tool_calls = getattr(ai_message, "tool_calls", None)
            if not tool_calls:
                final_text = ai_message.content
                return AgentResponse(
                    response=final_text,
                    tool_calls=tool_call_trace or None,
                )

            for call in tool_calls:
                tool_name = call["name"]
                args = call.get("args") or {}
                tool_call_id = call.get("id")

                logger.info("Agent invoking tool {}", tool_name)
                tool = tools_by_name.get(tool_name)
                if tool is None:
                    logger.error("Requested unknown tool: {}", tool_name)
                    continue

                result = await tool.ainvoke(args)
                tool_result = AgentToolCallResult(
                    tool=tool_name,
                    args=args,
                    result=result,
                )
                tool_call_trace.append(tool_result)

                if tool_call_id:
                    messages.append(
                        ToolMessage(
                            content=json.dumps(result),
                            tool_call_id=tool_call_id,
                        ),
                    )

            # Let the model see the last AI message as context as well.
            messages.append(ai_message)

        return AgentResponse(
            response="The agent could not complete your request within the tool-calling limit.",
            tool_calls=tool_call_trace or None,
        )
    except HTTPException:
        # Let FastAPI HTTP errors bubble up unchanged.
        raise
    except Exception as exc:
        logger.exception("Error while handling agent query")
        raise HTTPException(
            status_code=500,
            detail="AI agent failed to process the request.",
        ) from exc

