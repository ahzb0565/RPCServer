package rpc;


public class AutomatorServiceImpl extends AutomatorService {

    final public static String STORAGE_PATH = "/data/local/tmp/";

	public AutomatorServiceImpl() {
	}

    /**
     * It's to test if the service is alive.
     *
     * @return 'pong'
     */
    @Override
    public String ping() {
        return "pong";
    }
}
