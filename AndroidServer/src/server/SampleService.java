package server;
import android.app.Notification;
import android.app.NotificationManager;
import android.app.Service;
import android.content.Context;
import android.content.Intent;
import android.os.IBinder;
import android.util.Log;
import rpc.RPCServer;

public class SampleService extends Service{
    private final static String TAG = "SampleService";
    private RPCServer rpc;
    NotificationManager mNotificationManager = null;

    @Override
    public IBinder onBind(Intent intent) {
        // TODO Auto-generated method stub
        Log.d(TAG, "onBind");
        return null;
    }
    
    @Override
    public void onCreate() {
        Log.d(TAG, "onCreate");
        super.onCreate();
    }
    
    @Override
    public void onStart(Intent intent, int startId){
        Log.d(TAG, "onStart");
        super.onStart(intent, startId);
        try {
            if(rpc == null){
                rpc = new RPCServer();
                rpc.start();
            }else if(!rpc.isAlive()){
                rpc.start();
            }
        } catch (Exception e) {
            // TODO Auto-generated catch block
            e.printStackTrace();
        }
        mNotificationManager = (NotificationManager) getSystemService(Context.NOTIFICATION_SERVICE);
        Notification noti = new Notification.Builder(this)
            .setContentTitle("Bob Service")
            .setContentText("Bob Service is Running...")
            .setSmallIcon(android.R.drawable.ic_dialog_info)
            .build();
        startForeground(1234, noti);
    }
    
    public void onStartCommond(Intent intent, int flags, int startId){
        Log.d(TAG, "onStartCommond");
        super.onStartCommand(intent, flags, startId);
    }

    @Override
    public void onDestroy() {
        Log.d(TAG, "onDestroy");
        stopForeground(true);
        mNotificationManager.cancelAll();
        super.onDestroy();
        if(rpc != null && rpc.isAlive()){
            try {
                rpc.stop();
            } catch (Exception e) {
                // TODO Auto-generated catch block
                e.printStackTrace();
            }
        }
    }
}
