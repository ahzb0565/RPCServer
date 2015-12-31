package rpc;

import server.SampleService;
import android.content.ServiceConnection;


public class AutomatorService {
    final static int ERROR_CODE_BASE = -32000;
    SampleService sampleService;

    AutomatorService () {

    }

    /**
     * It's to test if the service is alive.
     * @return 'pong'
     */
    public String ping() {
        return "pong";
    }
}
