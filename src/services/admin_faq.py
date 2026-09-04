from pravburo_ref_common.models import FaqItem
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession


async def list_faq_items(session: AsyncSession) -> list[FaqItem]:
    return list(
        (await session.scalars(select(FaqItem).order_by(FaqItem.position, FaqItem.id))).all()
    )


async def create_faq_item(session: AsyncSession, question: str, answer: str) -> None:
    next_position = (await session.scalar(select(func.max(FaqItem.position)))) or 0
    session.add(
        FaqItem(question=question.strip(), answer=answer.strip(), position=next_position + 1)
    )
    await session.commit()


async def update_faq_item(session: AsyncSession, item_id: int, question: str, answer: str) -> None:
    item = await session.get(FaqItem, item_id)
    if item is not None:
        item.question = question.strip()
        item.answer = answer.strip()
        await session.commit()


async def delete_faq_item(session: AsyncSession, item_id: int) -> None:
    item = await session.get(FaqItem, item_id)
    if item is not None:
        await session.delete(item)
        await session.commit()


async def move_faq_item(session: AsyncSession, item_id: int, direction: str) -> None:
    items = await list_faq_items(session)
    index = next((i for i, item in enumerate(items) if item.id == item_id), None)
    if index is None:
        return
    swap_index = index - 1 if direction == "up" else index + 1
    if swap_index < 0 or swap_index >= len(items):
        return
    items[index].position, items[swap_index].position = (
        items[swap_index].position,
        items[index].position,
    )
    await session.commit()
