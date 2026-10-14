"""The native controller protocol. The HTTP Pi endpoint is separate from this gRPC hop."""
import grpc
from google.protobuf import descriptor_pool, json_format, message_factory
import a2a_pb2
from kagent.api.v1alpha1 import sessions_pb2, system_pb2, agents_pb2

EXT = 'https://kagent.dev/extensions/hitl/v1'


class RPC:
    def __init__(self, address):
        self.channel = grpc.insecure_channel(address)

    def call(self, service, method, body, timeout=35):
        descriptor = descriptor_pool.Default().FindServiceByName(service).methods_by_name[method]
        request = message_factory.GetMessageClass(descriptor.input_type)()
        json_format.ParseDict(body, request)
        response_type = message_factory.GetMessageClass(descriptor.output_type)
        call = self.channel.unary_unary('/'+service+'/'+method,
            request_serializer=lambda value: value.SerializeToString(), response_deserializer=response_type.FromString)
        result = call(request, timeout=timeout, metadata=(('a2a-extensions', EXT),))
        return json_format.MessageToDict(result, always_print_fields_with_no_presence=True)
