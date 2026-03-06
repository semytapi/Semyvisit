from flask import Flask, jsonify, request
import aiohttp
import asyncio
import json
from byte import encrypt_api, Encrypt_ID
from visit_count_pb2 import Info

app = Flask(__name__)

TARGET_VISITS = 2000
BATCH_SIZE = 200   # Vercel safe

def load_tokens(server):
    try:
        if server == "IND":
            path = "token_ind.json"
        elif server in {"BR","US","SAC","NA"}:
            path = "token_br.json"
        else:
            path = "token_bd.json"

        with open(path) as f:
            data = json.load(f)

        return [i["token"] for i in data if "token" in i and i["token"]]
    except:
        return []

def get_url(server):

    if server == "IND":
        return "https://client.ind.freefiremobile.com/GetPlayerPersonalShow"

    elif server in {"BR","US","SAC","NA"}:
        return "https://client.us.freefiremobile.com/GetPlayerPersonalShow"

    return "https://clientbp.ggblueshark.com/GetPlayerPersonalShow"


def parse_player(data):

    try:
        info = Info()
        info.ParseFromString(data)

        return {
            "uid": info.AccountInfo.UID,
            "nickname": info.AccountInfo.PlayerNickname,
            "likes": info.AccountInfo.Likes,
            "region": info.AccountInfo.PlayerRegion,
            "level": info.AccountInfo.Levels
        }

    except:
        return None


async def visit(session,url,token,data):

    headers={
        "ReleaseVersion":"OB52",
        "X-GA":"v1 1",
        "Authorization":f"Bearer {token}",
        "Host":url.replace("https://","").split("/")[0]
    }

    try:

        async with session.post(url,headers=headers,data=data,ssl=False) as r:

            if r.status==200:
                return True,await r.read()

    except:
        pass

    return False,None


async def run_visits(tokens,uid,server):

    url=get_url(server)

    encrypted = encrypt_api("08"+Encrypt_ID(str(uid))+"1801")
    data = bytes.fromhex(encrypted)

    success=0
    sent=0
    player=None

    connector=aiohttp.TCPConnector(limit=500)

    async with aiohttp.ClientSession(connector=connector) as session:

        while success<TARGET_VISITS:

            tasks=[]

            for i in range(BATCH_SIZE):

                token=tokens[(sent+i)%len(tokens)]

                tasks.append(
                    asyncio.create_task(
                        visit(session,url,token,data)
                    )
                )

            results=await asyncio.gather(*tasks)

            for ok,res in results:

                if ok:
                    success+=1

                    if not player and res:
                        player=parse_player(res)

            sent+=BATCH_SIZE

            if success>=TARGET_VISITS:
                break

    return success,player


@app.route("/semy")

def api():

    uid=request.args.get("uid")
    server=request.args.get("server")

    if not uid or not server:
        return jsonify({"error":"uid and server required"})

    uid=int(uid)
    server=server.upper()

    tokens=load_tokens(server)

    if not tokens:
        return jsonify({"error":"tokens not found"})

    success,player=asyncio.run(run_visits(tokens,uid,server))

    if not player:
        return jsonify({"error":"decode failed"})

    return jsonify({
        "uid":player["uid"],
        "nickname":player["nickname"],
        "likes":player["likes"],
        "level":player["level"],
        "region":player["region"],
        "success":success,
        "fail":TARGET_VISITS-success
    })


app = app