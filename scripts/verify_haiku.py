"""One small paid integration check; never creates or changes library entries."""
from haiku_client import MODEL, request_json
value=request_json('Return exactly this JSON object: {"connection":"ok"}.')
if value.get('connection')!='ok':
    raise RuntimeError('The Haiku connection response was not valid')
print('Connected to '+MODEL+' through the Inspire Worker. No library entries changed.')
