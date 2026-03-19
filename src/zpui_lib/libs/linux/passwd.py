from zpui_lib.helpers import ProHelper, setup_logger
from time import sleep, time

logger = setup_logger(__name__, "debug")

def passwd(username, password, timeout=10):
    """
    returns a list of three values:
    0 - True/False for success/apparent failure
    1 - string describing the success/failure mode
    2 - list of all unexpected output
    """
    ph = None
    status = ["unknown"] # hack, explained below
    def process_output(output):
        output = output.strip().lower()
        logger.debug("calling process_output with {}".format(repr(output)))
        if "retype" in output and "new" in output and "password" in output:
            #output.startswith("Retype new UNIX password:") or output.startswith("Retype new password:"):
            status[0] = "repeat"
        elif "retype" not in output and "new" in output and "password" in output:
            # output.startswith("Enter new UNIX password:") or output.startswith("New password:"):
            status[0] = "enter"
        elif "password updated successfully" in output:
            status[0] = "success"
        else:
            # Unexpected output, let's append it to status and stop the process
            status.append(output)
            logger.debug("killing process")
            ph.kill_process()
            status[0] = "killed"
        logger.debug("current status: {}".format(status[0]))
    ph = ProHelper(["passwd", username], output_callback=process_output)
    start_time = time()
    ph.run()
    while ph.is_ongoing():
        ph.poll() # go through output and call process_output on it
        if status[0] in ["enter", "repeat"]:
            ph.write(password+'\n')
            status[0] = "waiting" # so that we don't send the password more than necessary
        elif status[0] == "success":
            pass # By this time, we've probably finished, next cycle of "while" will not happen
        sleep(0.1)
    ph.poll() # Process leftover output so that we can check for success/failure
    if timeout and time() - start_time >= timeout:
        return [False, "timeout", status[1:]]
    return [True if status[0] == "success" else False, status[0], status[1:]]
