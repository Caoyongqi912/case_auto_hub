#!/usr/bin/env python# -*- coding:utf-8 -*-# @Time : 2024/1/3# @Author : cyq# @File : miniFlask# @Software: PyCharm# @Desc:import jsonimport timefrom flask import Flask, request, jsonify, redirect, url_forfrom flask_cors import CORSfrom flask import Responseapp = Flask("miniFlask")app.config['JSON_AS_ASCII'] = FalseCORS(app, supports_credentials=True)@app.route("/mini/login", methods=["POST"])def login():    try:        parse = request.get_json()        username = parse.get("username")        password = parse.get("password")        return jsonify({"code": 0, "data": {"info": {"name": username, "password": password, "age": 20}, "number": 200,                                            "flag": True,                                            "list": [1, "name", True, {"hello": "world"}]}, "msg": "success"})    except Exception:        return jsonify({"code": 100, "data": None, "msg": "error"})@app.route("/mini/formDataReq", methods=['POST'])def f_data():    data = request.form    print(data)    return jsonify({"code": 0, "data": data, "msg": "ok"})@app.route("/mini/queryUser", methods=["GET"])def queryUser():    try:        token = request.headers.get("token")        if token == "im dsadkjhaskjdhaskjhd":            users = []            for i in range(10):                users.append({"username": "asd", "age": i})            return jsonify({"code": 0, "data": users, "msg": "success"})        else:            return jsonify({"code": 100, "data": None, "msg": "token error"})    except Exception as e:        print(e)        return jsonify({"code": 100, "data": None, "msg": "error"})@app.route("/mini/timeout", methods=["GET"])def timeout():    time.sleep(10)    return jsonify({"code": 0, "data": "123", "msg": "success"})@app.route("/mini/serverError", methods=["GET"])def serverError():    return jsonify({"code": 0, "data": 1 / 0, "msg": "success"})@app.route("/mini/forbidden", methods=["GET"])def forbidden():    return Response(json.dumps({"code": 100, "data": None, "msg": "auth error"}), status=403)@app.route("/mini/text", methods=["get"])def text():    time.sleep(4)    return "kdjakjdhakjhdakjdhajkdhiu,kfghdkghdkladkas"@app.route("/login", methods=['POST'])def r0():    return redirect(url_for("r1"))@app.route("/red_1")def r1():    time.sleep(1)    return redirect(url_for("r2"))@app.route("/red_2")def r2():    time.sleep(1)    return redirect(url_for("r3"))@app.route("/red_3")def r3():    return jsonify(dict(        code=0,        data="dsadkjhaskjdhaskjhd",        msg="ok"    ))if __name__ == '__main__':    app.run(host="127.0.0.1", port=6006)