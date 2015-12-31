package rpc;

import java.io.*;
import java.util.HashMap;
import java.util.Map;

import com.googlecode.jsonrpc4j.JsonRpcServer;

import fi.iki.elonen.NanoHTTPD;

public class AutomatorHttpServer extends NanoHTTPD {

    public AutomatorHttpServer(int port) {
        super(port);
    }

    private Map<String, JsonRpcServer> router = new HashMap<String, JsonRpcServer>();

    public void route(String uri, JsonRpcServer rpc) {
        router.put(uri, rpc);
    }

    public Response serve(String uri, Method method,
                          Map<String, String> headers, Map<String, String> params,
                          Map<String, String> files) {
        Log.d(String.format("URI: %s, Method: %s, Header: %s, params, %s, files: %s", uri, method, headers, params, files));

        if ("/stop".equals(uri)) {
            stop();
            return new Response("Server stopped!!!");
        } else if (router.containsKey(uri)) {
            JsonRpcServer jsonRpcServer = router.get(uri);
            ByteArrayInputStream is = null;
            if (params.get("NanoHttpd.QUERY_STRING") != null)
                is = new ByteArrayInputStream(params.get("NanoHttpd.QUERY_STRING").getBytes());
            else if (files.get("postData") != null)
                is = new ByteArrayInputStream(files.get("postData").getBytes());
            else
                return new Response(Response.Status.INTERNAL_ERROR, MIME_PLAINTEXT, "Invalid http post data!");
            ByteArrayOutputStream os = new ByteArrayOutputStream();
            try {
                jsonRpcServer.handle(is, os);
                return new Response(Response.Status.OK, "application/json", new ByteArrayInputStream(os.toByteArray()));
            } catch (IOException e) {
                return new Response(Response.Status.INTERNAL_ERROR, MIME_PLAINTEXT, "Internal Server Error!!!");
            }
        } else
            return new Response(Response.Status.NOT_FOUND, MIME_PLAINTEXT, "Not Found!!!");
    }
}
