package rpc;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.googlecode.jsonrpc4j.JsonRpcServer;
import rpc.Log;

/**
 * A working example of a ui automator test.
 * 
 * @author SNI
 */
public class RPCServer {
    private static final int PORT = 9083;
    private AutomatorHttpServer server = null;

    public void start() throws Exception {
        Log.i("Start RPC server");
        server = new AutomatorHttpServer(PORT);
        server.route("/jsonrpc/0", new JsonRpcServer(new ObjectMapper(),
                new AutomatorService(), AutomatorService.class));
        server.start();
    }

    public void stop() throws Exception {
    	Log.i("Stop RPC server");
        if (server != null) {
            server.stop();
            server = null;
        }
    }

    public boolean isAlive() {
        if (server == null) {
            return false;
        } else {
            return server.isAlive();
        }
    }
}
