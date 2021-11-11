# noinspection PyUnresolvedReferences,PyUnusedLocal,PyUnboundLocalVariable
async def handler(action: Action, conn: Connection):
    data = action.data
    data_type = action.data_type
    data_len = action.data_len
    return Action({
        "Hello": "World!"
    }, status=300)


# noinspection PyUnresolvedReferences,PyUnusedLocal
class Connection:
    async def handle(self):
        action_type_id = self.read(1)
        action_type = self.conf.actions.find(action_type_id)
        action_gen = action_type.from_buffer()
        try:
            to_read = next(action_gen)
            while True:
                if isinstance(to_read, int):
                    part = self.read(to_read)
                else:
                    part = self.read_until(to_read)
                action_gen.send(part)
        except StopIteration:
            action = action_gen.value

        result: Action | None = await handler(action, conn)
        if result is None:
            return

        result.handler_id = action.handler_id
        result.message_id = action.message_id
        result.offset = action.offset
        await self.send(result)

    async def send(self, action: Action):
        ????????
